# I18n 开发规范

本文档定义 `packages/gui` 前端国际化（Vue I18n）的开发规范与核心要点。
详细架构设计参见 [设计文档：i18n 实现](../design/zh-CN_i18n_implementation.md)。

---

## 核心要点（开发必须遵守）

### 1. 禁止在源码中硬编码任何用户可见的字符串

所有出现在 UI 上的文本（标签、按钮、提示、占位符、标题、错误信息等）
**必须**通过 `t()` 函数从语言包中读取，绝对不能直接写在 `.vue` 或 `.ts` 文件内。

```ts
// ❌ 禁止
<button>保存</button>
<button>Save</button>
successMessage.value = '设置已保存'

// ✅ 正确
<button>{{ t('common.save') }}</button>
successMessage.value = t('settings.settingsSaved')
```

### 2. 新增 UI 文本时必须同步维护两个语言包

每次向 `en.json` 添加新 key，必须同时在 `zh.json` 中添加对应翻译，
保持两个文件键结构**完全一致**。

```bash
# 快速验证两个文件的顶层 key 是否一致
node -e "
const en = require('./src/i18n/locales/en.json');
const zh = require('./src/i18n/locales/zh.json');
const diff = Object.keys(en).filter(k => !(k in zh));
console.log(diff.length ? 'Missing zh keys: ' + diff : 'OK');
"
```

### 3. zh.json 使用 UTF-8 中文字符，禁止 Unicode 转义

`zh.json` 文件直接存储中文字符，**不使用** `\uXXXX` 转义。
这样可以保证：
- IDE 内直接可读，便于翻译维护
- Git diff 显示真实文案变化
- 全局搜索中文字符串可命中 JSON 文件

> `check_language.py` 仅扫描 `.py`、`.ts`、`.vue` 三类文件，
> JSON 文件中的中文字符不受限制。

### 4. i18n key 命名规范

- 使用 **小写 camelCase**，按模块分层，用 `.` 分隔
- 一级 key 按功能模块划分：`common`、`settings`、`sidebar`、`chat`、`workspace`、`widgets`、`errors`
- 插值参数使用 `{paramName}` 格式

```json
// 好的 key 命名示例
"chat.trace.completed"          // 模块.子模块.状态
"settings.cas.passwordLabel"    // 模块.子模块.元素
"errors.loadDeadlines"          // 错误类.具体错误
```

### 5. 组件中使用 Composition API

```vue
<script setup lang="ts">
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
</script>
```

不使用 Options API 的 `$t()`（与 `legacy: false` 模式不兼容）。

### 6. 常量 key 优先提取为具名常量

对于在多处复用的 i18n key，提取为常量（参考 `settingsConstants.ts` 的
`SETTINGS_SECTION_I18N_KEYS`）：

```ts
// settingsConstants.ts
export const SETTINGS_SECTION_I18N_KEYS: Record<SettingsSection, string> = {
  [SETTINGS_SECTIONS.CAS_SERVICE]: 'settings.sections.casService',
  // ...
}

// 组件中
t(SETTINGS_SECTION_I18N_KEYS[section])
```

### 7. Vitest 测试中 mock vue-i18n

由于 Pinia store 使用 `useI18n()`，单元测试必须 mock：

```ts
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
  createI18n: () => ({}),
}))
```

`t()` 返回 key 本身，测试断言使用 key 字符串（如 `'settings.settingsSaved'`）
而非翻译后的实际文本，保持测试与语言无关。

---

## 参考资料

- [设计文档：Vue I18n 实现详解](../design/zh-CN_i18n_implementation.md)
- [Vue I18n 官方文档](https://vue-i18n.intlify.dev/)
- [Vue 代码规范](zh-CN_code_conventions_vue.md)
