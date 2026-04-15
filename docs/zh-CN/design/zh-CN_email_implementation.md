# Email 功能实现详解

本文档描述邮件收发功能（A005 / A006）的完整技术实现，涵盖数据模型、持久化层、IMAP 客户端、服务层、REST API 及 Vue3 前端。

---

## 1. 架构总览

```
┌────────────────────────────────────────────────────────────────┐
│                        Vue3 Frontend                           │
│  InboxWidget.vue  ComposeEditor.vue  useToast.ts               │
│  stores/email.ts (Pinia)  api/email.ts (fetch)                 │
└────────────────┬───────────────────────────┬───────────────────┘
                 │  REST / JSON              │
┌────────────────▼───────────────────────────▼───────────────────┐
│              FastAPI  —  api/routes/email.py                   │
│  POST /sync  GET /email  GET /{uid}  PATCH /{uid}/flags        │
│  POST /{uid}/attachments/{att_id}/download  POST /send …       │
└──────────────────────────┬─────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────┐
│              EmailService  (services/email_service.py)         │
│  sync_emails  ensure_email_content_fetched  update_flag        │
│  download_attachment  send_email  …                            │
└──────────┬───────────────────────────────────┬─────────────────┘
           │                                   │
┌──────────▼──────────┐             ┌──────────▼──────────────────┐
│  EmailClient        │             │  EmailStore                 │
│  (IMAP / SMTP)      │             │  (SQLite via SQLModel)      │
│  email_client.py    │             │  email_store.py             │
└─────────────────────┘             └─────────────────────────────┘
```

- **Controller**：FastAPI 路由，输入校验，HTTP 错误映射
- **Service**：业务逻辑协调，跨 Client + Store 编排
- **Client**：纯 IMAP/SMTP I/O（`asyncio.to_thread` 包装同步 `imaplib`）
- **Store**：SQLite 持久化（SQLModel async ORM，`aiosqlite` 驱动）


---

## 2. 数据模型

文件：`packages/core/src/agent_core/models/email.py`

### 2.1 枚举

| 枚举 | 成员 | 说明 |
|------|------|------|
| `EmailFlag` | `SEEN / FLAGGED / ANSWERED / DELETED / SPAM` | IMAP 标志标识符，用于标志切换 API |
| `MailboxFolder` | `INBOX / SENT / TRASH / SPAM / STARRED` | Tencent Exmail IMAP 文件夹名；`STARRED` 是虚拟文件夹 |
| `ImapDefaults` | `IMAP_HOST / IMAP_PORT / SMTP_HOST / SMTP_PORT` | 集中管理服务器连接参数，消除魔法字符串 |

`STARRED = "__STARRED__"` 不对应真实 IMAP 文件夹，由 Service 层翻译为 `SEARCH FLAGGED` 指令。

### 2.2 ORM 表：`EmailRecord`

表名：`emails`。主键为复合键 `(uid, folder)`，支持同一封邮件在不同文件夹中独立存储（如 Sent Messages）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `uid` | `int` PK | IMAP UID |
| `folder` | `str` PK | IMAP 文件夹路径，默认 `"INBOX"` |
| `message_id` | `str` | RFC-2822 Message-ID |
| `subject / sender / sender_name` | `str` | 邮件头字段 |
| `recipients / cc` | `str` | 逗号分隔的收件人地址 |
| `date` | `str` | ISO-8601 日期字符串 |
| `body_text` | `str` | 纯文本正文（或 HTML→text 回退） |
| `html_local_path` | `str` | 缓存 HTML 文件的相对路径 |
| `is_seen / is_flagged / is_answered` | `bool` | IMAP 标志位 |
| `has_attachments` | `bool` | 快速列表展示用的便捷标志 |
| `content_fetched` | `bool` | 懒加载状态：`True` 表示 HTML 和附件已下载 |
| `synced_at` | `str` | 最后同步时间戳 |

### 2.3 ORM 表：`AttachmentRecord`

表名：`attachments`。代理主键 `id`，通过 `(email_uid, email_folder)` 关联邮件。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `int` PK (auto) | 代理主键 |
| `email_uid / email_folder` | `int / str` | 外键复合引用 |
| `filename` | `str` | 原始文件名 |
| `content_type` | `str` | MIME 类型 |
| `content_id` | `str` | RFC-2392 CID（内联图片） |
| `local_path` | `str` | 缓存路径 |
| `file_size` | `int` | 字节数 |
| `is_downloaded` | `bool` | `False`=仅元数据存根，`True`=文件已存入磁盘 |


---

## 3. 持久化层：EmailStore

文件：`packages/core/src/agent_core/persistence/email_store.py`

### 3.1 初始化与迁移

`EmailStore.initialize()` 在启动时调用，执行：
1. `SQLModel.metadata.create_all()` — 创建表（幂等）
2. `_migrate()` — 通过 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 补全历史数据库缺失的列（`folder`、`is_downloaded`、`email_folder` 等）

> **原因**：SQLModel 不自带迁移工具，用轻量级 SQL 补丁替代 Alembic，符合项目"避免过度工程化"原则。

### 3.2 upsert_email — 保留策略

```python
_preserve_if_truthy = frozenset(
    {"content_fetched", "html_local_path", "body_text"}
)
```

同步时 IMAP 拉取的数据会覆盖本地记录，**但以上三个字段是例外**：

| 字段 | 保留条件 | 原因 |
|------|----------|------|
| `content_fetched` | 本地为 `True`，新值为 `False` | 防止同步清除已懒加载的内容 |
| `html_local_path` | 本地非空，新值为空 | 防止同步清除已缓存 HTML 路径 |
| `body_text` | 本地非空，新值为空 | 防止头部同步（无正文）覆盖懒加载时写入的正文 |

> **注意**：`is_seen` **不在**保留列表中。同步总是以 IMAP 服务器的 FLAGS 为准，这样才能正确同步"另一个客户端标记未读"的状态。

### 3.3 主要方法速览

| 方法 | 说明 |
|------|------|
| `upsert_email(record)` | 按 `(uid, folder)` 插入或更新 |
| `get_email(uid, folder)` | 按复合键查询单封 |
| `list_emails(folder, unread_only, flagged_only, limit)` | 多条件列表查询 |
| `update_flags(uid, current_folder, *, is_seen, is_flagged, ...)` | 就地更新标志位 |
| `mark_content_fetched(uid, html_path, body_text, folder)` | 标记懒加载完成，同时持久化正文 |
| `reset_cache_fields()` | 清空 `content_fetched` / `html_local_path` / `is_downloaded`（缓存清除时用） |
| `upsert_attachment(att)` | 插入或更新附件记录 |
| `mark_attachment_downloaded(att_id, path, size)` | 将存根标记为已下载 |


---

## 4. IMAP 客户端：EmailClient

文件：`packages/core/src/agent_core/services/email_client.py`

### 4.1 线程模型

所有 IMAP/SMTP 操作都是阻塞 I/O。项目通过 `asyncio.to_thread()` 包装同步方法，保持 FastAPI 事件循环不阻塞：

```
async def fetch_emails(...)  →  asyncio.to_thread(_sync_fetch_emails, ...)
async def set_flag(...)      →  asyncio.to_thread(_sync_set_flag, ...)
```

### 4.2 文件夹名引号处理

Tencent Exmail 的文件夹名包含空格（如 `"Sent Messages"`）。不加引号会导致 IMAP 命令解析失败：

```python
def _imap_quote(folder: str) -> str:
    """如果文件夹名含空格，用双引号包裹，符合 RFC 3501 quoted-string 规范。"""
    return f'"{folder}"' if " " in folder else folder
```

所有 `imap.select()` 调用均通过此函数处理文件夹名。

### 4.3 邮件列表同步（fetch_emails）

1. `imap.select(folder, readonly=True)` — 只读模式，不修改服务器标志
2. `SEARCH SINCE <date>` 获取 UID 列表
3. `STARRED` 虚拟文件夹 → `SEARCH FLAGGED` in INBOX
4. `UID FETCH <num> (UID FLAGS RFC822.HEADER)` — 仅拉取头部和标志，不拉取正文
5. 解析为 `EmailRecord`，`content_fetched=False`，`body_text=""`

> **重要**：fetch spec 中 FLAGS 必须写在 RFC822.HEADER **前面**。Tencent Exmail 的 IMAP 实现在 `(UID RFC822 FLAGS)` 格式下会把 FLAGS 放入响应末尾的独立 bytes 项中（而非 metadata tuple），导致 `_parse_flags_from_meta` 始终解析为空字符串。正确格式 `(UID FLAGS RFC822.HEADER)` 会将 FLAGS 放入 metadata tuple，可被可靠解析。

### 4.4 邮件内容懒加载（fetch_email_content）

1. `imap.select(folder)` — **读写模式**（不传 `readonly=True`）
2. `UID FETCH <uid> (RFC822)` — 拉取完整 MIME 消息
3. `_process_body_attachments()` — 解析 MIME tree：
   - 内联图片（`content-disposition: inline` 或有 Content-ID）→ 立即下载并保存
   - 普通附件 → 创建 `AttachmentRecord(is_downloaded=False)` 存根
4. 提取 HTML/text body，保存为 `cache/email/html/<uid>.html`
5. 返回 `(html_local_path, att_records, body_text)` 三元组

`body_text` 由 Service 层传递给 `store.mark_content_fetched()` 持久化，后续 `upsert_email`（头部同步）不会覆盖它（`body_text` 在 `_preserve_if_truthy` 中）。

### 4.5 附件按需下载（download_attachment_file）

用户点击下载时才真正拉取附件内容：

1. `imap.select(folder)` — **读写模式**
2. `UID FETCH <uid> (BODY[])` — 拉取完整消息
3. 按 `filename` 在 MIME tree 中找到目标部分
4. 解码并写入 `cache/email/attachments/<uid>_<filename>`
5. 返回本地路径和文件大小

### 4.6 标志操作（set_flag / expunge / copy_to_folder）

| 方法 | IMAP 指令 | 用途 |
|------|-----------|------|
| `set_flag(uid, flag, True/False)` | `UID STORE uid +FLAGS/-FLAGS (\Flag)` | 标记已读/未读/星标/删除 |
| `expunge(uid, folder)` | `UID STORE ... +FLAGS (\Deleted)` → `EXPUNGE` | 永久删除 |
| `copy_to_folder(uid, src, dst)` | `UID COPY uid dst` | 移动到垃圾箱/垃圾邮件（配合删除） |

### 4.7 IMAP FLAG_MAP

```python
IMAP_FLAG_MAP: dict[EmailFlag, str] = {
    EmailFlag.SEEN:     "\\Seen",
    EmailFlag.FLAGGED:  "\\Flagged",
    EmailFlag.ANSWERED: "\\Answered",
    EmailFlag.DELETED:  "\\Deleted",
}
```

`SPAM` 不是标准 IMAP 标志，由 Service 层翻译为"复制到 Junk 文件夹 + 删除原邮件"。


---

## 5. 服务层：EmailService

文件：`packages/core/src/agent_core/services/email_service.py`

EmailService 是唯一与 Controller 交互的业务层，协调 Client 和 Store。

### 5.1 凭据管理

```python
async def _get_credentials(self) -> tuple[str, str]:
    ...
```

从 `ProfileStore` 获取加密存储的 `email_account` / `email_password`。若未配置则抛出 `ValueError`，Controller 捕获后返回 HTTP 428（`EMAIL_CREDENTIALS_MISSING`）。

### 5.2 邮件同步流程

```
sync_emails(days, folder)
  └─ _get_credentials()
  └─ client.fetch_emails(account, password, days, folder)
     └─ IMAP: SELECT → SEARCH SINCE → FETCH FLAGS+HEADER
  └─ for each record: store.upsert_email(record)
  └─ 返回 EmailSyncResult
```

`STARRED` 文件夹同步时映射到 INBOX（服务器上没有独立文件夹）：
```python
imap_folder = "INBOX" if folder == "__STARRED__" else folder
```

### 5.3 内容懒加载流程（ensure_email_content_fetched）

```
ensure_email_content_fetched(uid, folder)
  └─ store.get_email(uid, folder)       # 检查本地缓存
  └─ if not content_fetched:
     └─ client.fetch_email_content(...)  # IMAP RFC822 → (html_path, att_records, body_text)
     └─ store.upsert_attachment(att)     # for each attachment stub
     └─ store.mark_content_fetched(uid, html_path, body_text=body_text)
     └─ if not is_seen:
        └─ client.set_flag(SEEN=True)   # 显式 IMAP STORE +FLAGS (\Seen)
        └─ store.update_flags(is_seen=True)
  └─ get_email_detail(uid, folder)      # 返回完整详情
```

> **关键设计**：先显式调用 IMAP STORE，再更新本地库。Tencent Exmail 于 RFC822 拉取时不会隐式设置 `\Seen`，必须用显式 STORE 指令。

### 5.4 标志更新（update_flag）

| 标志 | 行为 |
|------|------|
| `SEEN / FLAGGED / ANSWERED` | `client.set_flag()` → `store.update_flags()` |
| `DELETED=True` | `client.set_flag(DELETED)` → `client.expunge()` → `store.update_flags(folder=Trash)` |
| `SPAM=True` | `client.copy_to_folder(src=folder, dst="Junk")` → `client.set_flag(DELETED)` → `client.expunge()` → `store.update_flags(folder=Spam)` |

### 5.5 附件下载（download_attachment）

```
download_attachment(uid, att_id)
  └─ store.get_attachment(att_id)
  └─ if is_downloaded: return cached record
  └─ client.download_attachment_file(uid, filename, folder)
  └─ store.mark_attachment_downloaded(att_id, path, size)
  └─ return updated AttachmentRecord
```


---

## 6. REST API

文件：`packages/core/src/agent_core/api/routes/email.py`，前缀 `/api/email`

| 方法 | 路径 | Query 参数 | 说明 |
|------|------|-----------|------|
| `POST` | `/sync` | `days?`, `folder?` | 触发 IMAP 同步 |
| `GET` | `` (空) | `folder?`, `unread_only?`, `flagged_only?`, `limit?` | 列出邮件摘要 |
| `GET` | `/count` | — | 本地邮件总数 |
| `GET` | `/{uid}` | `folder` | 获取邮件详情（触发懒加载） |
| `GET` | `/{uid}/html` | `folder` | 返回 HTML 文件（内联图片 CID 替换） |
| `GET` | `/{uid}/attachments/{att_id}` | — | 流式下载已缓存附件 |
| `POST` | `/{uid}/attachments/{att_id}/download` | — | 触发按需附件下载（返回 AttachmentRecord） |
| `PATCH` | `/{uid}/flags` | `folder` | 更新单个标志（body: `UpdateFlagRequest`） |
| `POST` | `/send` | — | 发送邮件（SMTP） |
| `POST` | `/test-connection` | — | 测试 IMAP/SMTP 连接 |
| `GET` | `/settings/email` | — | 获取邮件设置 |
| `PUT` | `/settings/email` | — | 更新邮件设置 |
| `DELETE` | `/cache` | — | 清除本地缓存（重置 `content_fetched`） |

### 错误映射

```python
def _raise_credentials_http_error(exc: ValueError) -> None:
    # 未配置凭据 → HTTP 428 Precondition Required + {code: EMAIL_CREDENTIALS_MISSING}
```

凭据未配置时，所有需要 IMAP 的端点返回 428（`EMAIL_CREDENTIALS_MISSING`），前端 InboxWidget 显示设置引导弹窗。


---

## 7. Vue3 前端

### 7.1 API 层（api/email.ts）

封装所有后端 REST 调用，使用原生 `fetch`。关键接口：

```typescript
interface EmailSummary {
  uid: number; folder: string; subject: string;
  sender: string; sender_name: string; date: string;
  is_seen: boolean; is_flagged: boolean; has_attachments: boolean;
  body_text: string;  // 前 200 字预览
}

interface AttachmentInfo {
  id: number; filename: string; content_type: string;
  file_size: number; is_downloaded: boolean;  // 新增：存根 vs 已下载
}
```

主要函数：

| 函数 | 方法 | 说明 |
|------|------|------|
| `syncEmails(days?, folder?)` | POST /sync | 触发 IMAP 同步 |
| `listEmails({folder?, unread_only?, flagged_only?})` | GET | 列表 |
| `getEmailDetail(uid, folder)` | GET /{uid} | 详情（触发懒加载） |
| `downloadAttachment(uid, attId)` | POST /{uid}/attachments/{attId}/download | 按需下载 |
| `updateEmailFlag(uid, flag, value, folder)` | PATCH /{uid}/flags | 标志切换 |

### 7.2 Pinia Store（stores/email.ts）

状态：

| 状态 | 类型 | 说明 |
|------|------|------|
| `emails` | `EmailSummary[]` | 当前文件夹的邮件列表 |
| `selectedEmail` | `EmailDetail \| null` | 当前选中邮件详情 |
| `currentFolder` | `string` | 当前文件夹，默认 `"INBOX"` |
| `selectingEmail` | `boolean` | 详情加载中（显示全屏遮罩） |
| `downloadingAtts` | `Set<number>` | 正在下载的附件 ID 集合 |
| `toasts` | `Toast[]` | 通知消息队列 |
| `folderCache` | `Map<string, EmailSummary[]>` | 各文件夹的本地缓存 |

关键动作：

```typescript
// 切换文件夹：先从缓存渲染，再后台更新
async setFolder(folder: string) {
  currentFolder.value = folder
  if (folderCache.has(folder)) emails.value = folderCache.get(folder)!
  await fetchEmails()
}

// 打开邮件（带 AbortController 支持取消）
async selectEmail(uid: number) {
  selectingEmail.value = true
  const ctrl = new AbortController()
  // ... fetch detail, update is_seen in local list
}

// 下载附件（追踪进行中状态）
async downloadAttachment(uid: number, attId: number) {
  downloadingAtts.value.add(attId)
  try { ... } finally { downloadingAtts.value.delete(attId) }
}
```

### 7.3 InboxWidget.vue 布局

```
┌──────────┬──────────────────────────────────┐
│ 文件夹   │ 邮件列表                          │
│ 侧边栏   ├───────────────────────────────────┤
│          │ 邮件详情（懒加载）                │
│ INBOX    │  正文 HTML（iframe 沙箱）         │
│ 发件箱   │  附件列表 + 按需下载按钮          │
│ ⭐已加星  ├───────────────────────────────────┤
│ 垃圾邮件 │ [全屏加载遮罩，含取消按钮]        │
│ 已删除   └───────────────────────────────────┘
└──────────────────────────────────────────────┘
         Toast 通知层（右下角浮动）
```

文件夹图标使用 Lucide：`Inbox / Send / Star / Trash2 / AlertOctagon`

### 7.4 ComposeEditor.vue（富文本编辑）

使用 `@wangeditor/editor` 的**原生 JS API**（而非 `editor-for-vue`），因为后者的 ESM 包含 `import t from "vue"` 会导致 Vite 构建失败：

```typescript
import { createEditor, createToolbar } from '@wangeditor/editor'

onMounted(() => {
  editor = createEditor({ selector: editorRef.value, ... })
  toolbar = createToolbar({ editor, selector: toolbarRef.value })
  editor.on('change', () => emit('update:modelValue', editor.getHtml()))
})
onBeforeUnmount(() => editor?.destroy())
```

通过 `v-model` 绑定到父组件的 `body_html` 字段。


---

## 8. 关键设计决策

### 8.1 复合主键 (uid, folder)

早期版本 `EmailRecord` 使用单字段主键 `uid`。当需要支持多文件夹（收件箱、发件箱等）时，同一 UID 在不同文件夹中可能指向不同邮件，因此改为 `(uid, folder)` 复合主键。

迁移策略：`_migrate()` 用 SQL ALTER TABLE 补列，不依赖 Alembic，保持轻量。

### 8.2 懒加载正文

列表同步只拉取邮件头和标志（`RFC822.HEADER`），体积小、速度快。只有用户点开某封邮件时，才触发 `fetch_email_content()` 下载完整正文和附件元数据（`is_downloaded=False` 存根）。

好处：大邮箱（数百封带附件的邮件）初始同步依然快速。

### 8.3 附件两阶段下载

| 阶段 | 触发 | 存储 |
|------|------|------|
| 存根创建 | 打开邮件详情时 | `is_downloaded=False`，无本地文件 |
| 文件下载 | 用户点击下载按钮 | `is_downloaded=True`，文件写入磁盘 |

内联图片（CID）在第一阶段即下载，以便 HTML 正确渲染。

### 8.4 `\Seen` 标志同步可靠性

**根本问题（A007h 发现）**：`_fetch_single_email` 最初使用 `FETCH (UID RFC822 FLAGS)`。在 Tencent Exmail 上，FLAGS 出现在响应末尾的独立 `bytes` 项中（`data[1]`），而非 metadata tuple（`data[0][0]`）。`_parse_flags_from_meta` 只读 tuple，导致**所有邮件的 `is_seen`、`is_flagged`、`is_answered` 永远为 `False`**，与服务器实际状态完全脱钩。

**标准 IMAP 服务器响应**（Gmail 等）：
```
data[0] = (b'3 (UID 4 FLAGS (\\Seen) RFC822 {2328}', <body>)  # FLAGS 在 tuple 里
```
**Tencent Exmail 响应**（`(UID RFC822 FLAGS)` 格式）：
```
data[0] = (b'3 (UID 4 RFC822 {2328}', <body>)  # tuple 里没有 FLAGS
data[1] = b'FLAGS ())'                          # 独立 bytes，且内容有时有误
```

**修复**：改用 `(UID FLAGS RFC822.HEADER)` — FLAGS 出现在 tuple 的 metadata 中，同时改为只拉取邮件头（体积小、速度快）：
```
data[0] = (b'3 (UID 4 FLAGS (\\Seen) RFC822.HEADER {1884}', <header>)  # FLAGS 可靠解析 ✓
```

**显式 `\Seen` 设置**：Tencent 不会在 RFC822 拉取时隐式设置 `\Seen`。`ensure_email_content_fetched` 在下载正文后用 `UID STORE +FLAGS (\Seen)` 显式告知服务器。

**`_preserve_if_truthy` 曾包含 `is_seen`（A007g 错误修复，已在 A007h 回退）**：  
该字段保留会导致"在另一个客户端标记未读"无法同步到本应用。正确策略是让 `is_seen` 始终由 IMAP sync 结果决定，同时依赖 `_preserve_if_truthy` 中的 `body_text` 保护已懒加载的正文不被头部同步覆盖。

### 8.5 `STARRED` 虚拟文件夹

Tencent Exmail 没有名为 `Starred` 的实体文件夹。实现方式：
- 同步时：在 INBOX 上执行 `SEARCH FLAGGED` 获取星标邮件
- 列表时：`list_emails(flagged_only=True)` 不过滤 folder，返回 INBOX 中 `is_flagged=True` 的邮件
- 前端：`setFolder("__STARRED__")` 传入特殊标识符

### 8.6 加密密钥持久化

默认 `Fernet` key 不持久化，服务重启后所有加密数据（邮箱密码）无法解密。修复：`_load_or_generate_key()` 在首次生成后写入 `output/.encryption_key`，后续重启读取同一密钥。

---

## 9. 常见陷阱

| 陷阱 | 症状 | 解决方案 |
|------|------|----------|
| IMAP 文件夹名含空格 | `NO [NONEXISTENT] Mailbox doesn't exist` | `_imap_quote()` 包裹双引号 |
| readonly=True 时拉取正文 | `\Seen` 未被设置 | 内容拉取必须用读写模式 `select(folder)` |
| `editor-for-vue` ESM 兼容 | Vite 构建时 `import t from "vue"` 报错 | 改用 `@wangeditor/editor` 原生 JS API |
| SQLModel 复合主键 | `upsert_email` 每次都 INSERT，出现重复记录 | `SELECT` 后手动 `setattr` 再 `session.add()` 模式 |
| `is_seen` 加入 `_preserve_if_truthy` | 跨客户端"标记未读"无法同步到本应用 | `is_seen` **不应**放入保留列表；FLAGS 始终以 IMAP 服务器为准 |
| Tencent `(UID RFC822 FLAGS)` 响应 | 所有邮件强制为未读、无星标 | 改为 `(UID FLAGS RFC822.HEADER)`，FLAGS 出现在 metadata tuple 中 |
| `body_text` 被头部同步覆写 | 打开过的邮件正文预览消失 | 将 `body_text` 加入 `_preserve_if_truthy`，并在 `mark_content_fetched` 时写入 |

