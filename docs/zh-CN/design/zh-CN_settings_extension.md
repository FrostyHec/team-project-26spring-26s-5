# Settings 设置功能 — 架构设计文档

## 概述

Settings 功能为用户提供 CAS（SUSTech 统一认证）与企业邮箱两组服务凭据的安全存储与管理。
当前扩展服务 section 还额外承担 YAML-backed LLM runtime 设置的维护，包括 provider 列表、temperature、max_iterations、system_prompt 与 `debug_mode`。
核心设计原则：

- **密码不出境**：密码仅单向写入，API 响应永不返回明文或密文，仅返回是否已设置的布尔标志
- **按需加密**：持久化层透明执行加密/解密，上层代码只处理明文
- **部分更新语义**：`PUT /settings` 仅更新请求体中非 `null` 的字段，未提及字段保持不变
- **单用户模型**：整个系统当前维护单条 Profile 记录（key/value 表），无多用户隔离需求

---

## 1. 后端架构

### 1.1 分层结构

```
packages/core/src/agent_core/
├── api/routes/settings.py      ← Controller 层：HTTP 路由、请求/响应 Pydantic 模型
├── models/settings.py          ← 数据模型：UserProfileRecord / UserProfileResponse / UpdateProfileRequest
├── persistence/profile_store.py ← Service/Store 层：SQLite 读写、加密调度
└── security/encryption.py      ← 加密基础设施：Fernet 对称加密
```

所有 API 路由通过 FastAPI 依赖注入 `ProfileStore` 实例，Controller 层不直接
接触数据库或加密逻辑：

```python
# routes/settings.py
@router.get("", response_model=UserProfileResponse)
async def get_settings(store: ProfileStore = Depends(get_profile_store)):
    record = await store.get_profile()
    return UserProfileResponse(
        cas_account=record.cas_account,
        cas_password_is_set=bool(record.cas_password_encrypted),
        ...
    )
```

### 1.2 数据模型

**`UserProfileRecord`**（内部存储模型，不暴露给 API）：

```python
class UserProfileRecord(BaseModel):
    cas_account: str = ""
    cas_password_encrypted: str = ""   # Fernet 密文
    email_account: str = ""
    email_password_encrypted: str = "" # Fernet 密文
```

**`UserProfileResponse`**（API 响应，密码字段只返回布尔值）：

```python
class UserProfileResponse(BaseModel):
    cas_account: str = ""
    cas_password_is_set: bool = False  # 永不返回密文
    email_account: str = ""
    email_password_is_set: bool = False
```

**`UpdateProfileRequest`**（API 请求，所有字段可选）：

```python
class UpdateProfileRequest(BaseModel):
    cas_account: str | None = None    # None = 不修改
    cas_password: str | None = None   # "" = 清空
    email_account: str | None = None
    email_password: str | None = None
```

### 1.3 ProfileStore 公开接口

`ProfileStore` 是唯一的持久化入口，Controller 层只调用以下方法：

| 方法 | 说明 |
|------|------|
| `await store.get_profile()` | 返回 `UserProfileRecord`（密文，不解密） |
| `await store.update_profile(cas_account=..., cas_password=..., ...)` | 部分更新，明文密码自动加密 |
| `await store.reset_profile()` | 清空所有字段，返回空 `UserProfileRecord` |
| `await store.get_decrypted_cas_password()` | 供内部服务调用（非 API 路由） |
| `await store.get_decrypted_email_password()` | 供内部服务调用（非 API 路由） |

`update_profile` 内部使用 `model_copy(update={...})` 做不可变更新，仅替换非 `None` 字段：

```python
async def update_profile(self, *, cas_account=None, cas_password=None, ...) -> UserProfileRecord:
    current = await self.get_profile()
    updated = current.model_copy(update={k: v for k, v in {...} if v is not None})
    if cas_password is not None:
        updated = updated.model_copy(update={"cas_password_encrypted": encrypt(cas_password)})
    await self.save_profile(updated)
    return updated
```

### 1.4 SQLite 存储方案

Profile 使用 key/value 表（与 SessionStore 共享同一 `sessions.db` 文件）：

```sql
CREATE TABLE IF NOT EXISTS user_profile (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
```

存储键由 `_ProfileKey` 内部枚举定义：

| 枚举值 | SQL key | 内容 |
|--------|---------|------|
| `CAS_ACCOUNT` | `cas_account` | 明文账号 |
| `CAS_PASSWORD_ENCRYPTED` | `cas_password_encrypted` | Fernet 密文 |
| `EMAIL_ACCOUNT` | `email_account` | 明文账号 |
| `EMAIL_PASSWORD_ENCRYPTED` | `email_password_encrypted` | Fernet 密文 |

Upsert 语句确保首次写入与更新使用同一路径：

```sql
INSERT INTO user_profile (key, value) VALUES (?, ?)
ON CONFLICT(key) DO UPDATE SET value = excluded.value;
```

### 1.5 加密方案

使用 `cryptography` 库的 `Fernet`（AES-128-CBC + HMAC-SHA256）：

- **密钥来源**：环境变量 `SETTINGS_ENCRYPTION_KEY`（URL-safe base64，32 字节熵）
- **降级行为**：变量缺失时自动生成临时密钥（进程内一致，重启后失效）；生产环境必须显式配置
- **接口**：`encrypt(plaintext: str) -> str` / `decrypt(ciphertext: str) -> str`
- **设计选择 Fernet 而非 bcrypt**：凭据需要可解密（供下游服务使用），故使用对称加密而非单向哈希

---

## 2. REST API 契约

所有端点挂载在 `/api/settings`（由 `APIRouter(prefix="/settings")` 定义，
主路由注册时加 `/api` 前缀）。

### `GET /api/settings`

读取当前用户 Profile。

**响应 200：**

```json
{
  "cas_account": "12345678",
  "cas_password_is_set": true,
  "email_account": "user@mail.sustech.edu.cn",
  "email_password_is_set": false
}
```

### `PUT /api/settings`

部分更新用户 Profile。`null` 字段不作修改；空字符串密码字段视为清空。

**请求体：**

```json
{
  "cas_account": "12345678",
  "cas_password": "s3cr3t",
  "email_account": null,
  "email_password": null
}
```

**响应 200：** 与 GET 相同的 `UserProfileResponse` 结构（更新后状态）。

**响应 500：** `{ "detail": "Failed to update settings" }`

### `DELETE /api/settings`

将 Profile 重置为初始空状态（清空所有字段）。

**响应 200：**

```json
{
  "cas_account": "",
  "cas_password_is_set": false,
  "email_account": "",
  "email_password_is_set": false
}
```

**响应 500：** `{ "detail": "Failed to reset settings" }`

---

## 3. 前端架构

### 3.1 分层结构

```
packages/gui/src/
├── api/settings.ts              ← HTTP 客户端：fetch 封装，类型化请求/响应
├── stores/settingsConstants.ts  ← 静态常量：section 标识符、i18n key 映射
├── stores/settings.ts           ← Pinia Store：状态管理、异步动作、locale 管理
└── components/settings/
    ├── SettingsPanel.vue        ← 设置面板容器（遮罩 + 主体布局）
    ├── SettingsSidebar.vue      ← 导航侧边栏（section 切换）
    ├── CasServiceSettings.vue   ← CAS 凭据面板
    ├── EmailServiceSettings.vue ← 邮箱凭据面板
    ├── ExtensionServiceSettings.vue ← LLM runtime / Provider / debug_mode 设置面板
    └── LanguageSettings.vue     ← 语言切换面板
```

### 3.2 API 客户端层（`api/settings.ts`）

前端类型定义与后端 Pydantic 模型一一对应：

```typescript
// 对应 UserProfileResponse
interface SettingsResponse {
  cas_account: string
  cas_password_is_set: boolean
  email_account: string
  email_password_is_set: boolean
}

// 对应 UpdateProfileRequest（所有字段可选）
interface UpdateSettingsRequest {
  cas_account?: string | null
  cas_password?: string | null
  email_account?: string | null
  email_password?: string | null
}
```

三个函数封装 HTTP 方法：

| 函数 | HTTP | 说明 |
|------|------|------|
| `getSettings()` | `GET /api/settings` | 读取 Profile |
| `updateSettings(req)` | `PUT /api/settings` | 部分更新 |
| `resetSettings()` | `DELETE /api/settings` | 清空所有凭据 |

### 3.3 Pinia Store（`stores/settings.ts`）

Store 使用 Composition API 风格（`defineStore` + `setup` 函数），对外暴露：

**状态（`ref`）：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `isOpen` | `boolean` | 设置面板是否展示 |
| `activeSection` | `SettingsSection` | 当前激活的导航 section |
| `profile` | `SettingsResponse \| null` | 已加载的 Profile 快照 |
| `isLoading` | `boolean` | 正在从后端加载 |
| `isSaving` | `boolean` | 正在保存到后端 |
| `isResetting` | `boolean` | 正在重置 |
| `error` | `string \| null` | 最后一次操作的错误信息 |
| `successMessage` | `string \| null` | 操作成功提示（3 秒后自动清除） |

**动作（异步）：**

| 方法 | 说明 |
|------|------|
| `openSettings()` | 展示面板并加载 Profile |
| `closeSettings()` | 关闭面板并清除临时状态 |
| `setActiveSection(section)` | 切换导航 section |
| `loadProfile()` | 调用 `getSettings()`，写入 `profile` |
| `saveProfile(request)` | 调用 `updateSettings()`，写入 `profile` + 成功提示 |
| `resetProfile()` | 调用 `resetSettings()`，清空 `profile` + 成功提示 |
| `setLocale(locale)` | 切换 Vue I18n locale 并持久化至 `localStorage` |
| `getLocale()` | 返回当前 locale 字符串 |

成功提示使用固定超时自动清除（`SUCCESS_MESSAGE_TIMEOUT_MS = 3000` ms）：

```typescript
successMessage.value = t('settings.settingsSaved')
setTimeout(() => { successMessage.value = null }, SUCCESS_MESSAGE_TIMEOUT_MS)
```

### 3.4 Section 常量与 i18n key 映射

`settingsConstants.ts` 定义 section 标识符（与后端 `SettingsCategory` 对齐），
并提供 i18n key 映射供组件渲染本地化标签：

```typescript
export const SETTINGS_SECTIONS = {
  CAS_SERVICE: 'cas_service',
  EMAIL_SERVICE: 'email_service',
  EXTENSION_SERVICE: 'extension_service',
  LANGUAGE: 'language',
} as const

export const SETTINGS_SECTION_I18N_KEYS: Record<SettingsSection, string> = {
  cas_service: 'settings.sections.casService',
  email_service: 'settings.sections.emailService',
  extension_service: 'settings.sections.extensionService',
  language: 'settings.sections.language',
}
```

组件通过 `t(SETTINGS_SECTION_I18N_KEYS[section])` 渲染本地化 section 名称，
避免在常量中硬编码任何语言相关字符串。

### 3.5 组件职责边界

| 组件 | 职责 |
|------|------|
| `SettingsPanel.vue` | 遮罩层、面板容器、调用 `openSettings`/`closeSettings` |
| `SettingsSidebar.vue` | 渲染 `SETTINGS_SECTION_LIST` 导航列表，调用 `setActiveSection` |
| `CasServiceSettings.vue` | 表单：账号/密码输入，调用 `saveProfile`/`resetProfile` |
| `EmailServiceSettings.vue` | 表单：同上，针对邮箱凭据 |
| `ExtensionServiceSettings.vue` | 占位面板，展示 Coming Soon 状态 |
| `LanguageSettings.vue` | 单选按钮切换 locale，调用 `setLocale`/`getLocale` |

---

## 4. 设计决策说明

| 决策 | 理由 |
|------|------|
| **Fernet 而非 bcrypt** | 凭据需可解密供下游服务（如邮件发送）使用，单向哈希不满足需求 |
| **key/value 表而非列表表** | 单用户 Profile 字段固定，key/value 方案无需 schema 迁移即可扩展新字段 |
| **密码不回传** | `UserProfileResponse` 永不包含密码字段，避免意外泄露于日志/网络 |
| **部分更新语义（`PUT`）** | 前端面板按 section 独立操作，不应强制携带所有字段；`null` 表示"不修改" |
| **`DELETE` 重置而非 `PUT` 空值** | 语义更明确：整体重置是破坏性操作，独立于部分更新路径 |
| **Store 管理 locale** | locale 切换需写入 `vue-i18n` 全局实例，Pinia Store 是唯一持有 `i18n` 引用的合适位置 |

---

## 5. 相关文档

- [Vue I18n 国际化实现详解](zh-CN_i18n_implementation.md) — 语言切换机制的架构设计
- [I18n 国际化开发规范](../devs/zh-CN_i18n.md) — 添加 i18n key 的开发规范
