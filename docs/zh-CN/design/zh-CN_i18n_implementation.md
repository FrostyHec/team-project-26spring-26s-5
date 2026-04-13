# Vue I18n 国际化实现文档

## 概述

`packages/gui` 前端采用 [Vue I18n v11](https://vue-i18n.intlify.dev/) 实现中英文
双语支持，默认界面语言为**英文**，用户可在设置面板中切换，偏好持久化至
`localStorage`。

---

## 架构

```
src/
├── i18n/
│   ├── index.ts              # Vue I18n 插件实例 + 工具函数导出
│   └── locales/
│       ├── en.json           # 英文语言包（默认）
│       └── zh.json           # 中文语言包（简体中文）
├── main.ts                   # app.use(i18n) 注册插件
└── components/
    └── settings/
        └── LanguageSettings.vue  # 用户语言切换 UI
```

### 核心模块：`src/i18n/index.ts`

```ts
export const LOCALE_STORAGE_KEY = 'app-locale'        // localStorage key
export const SUPPORTED_LOCALES = { EN: 'en', ZH: 'zh' } as const
export type SupportedLocale = 'en' | 'zh'

export interface LocaleEntry {
  code: SupportedLocale
  label: string              // 供 UI 显示的原生语言名称
}

export const LOCALE_ENTRIES: LocaleEntry[] = [
  { code: 'en', label: 'English' },
  { code: 'zh', label: '中文（简体）' },
]
```

插件以 **Composition API 模式**（`legacy: false`）初始化，启动时从
`localStorage` 读取用户上次选择的语言，回退至 `'en'`。

---

## 语言包结构

两个语言包（`en.json` / `zh.json`）保持**完全相同的键结构**，按功能模块
分层组织：

```json
{
  "common":    { "save", "reset", "close", "approve", "reject", ... },
  "settings":  { "title", "closeTitle", "sections.*", "cas.*", "email.*", "extension.*", "language.*" },
  "sidebar":   { "newChat", "noConversations", "deleteChat", "dateGroups.*", ... },
  "chat":      { "defaultTitle", "toggleSidebar", "inputPlaceholder", "trace.*", ... },
  "workspace": { "title", "refresh" },
  "widgets":   { "calendar", "calendarUpcoming", "calendarLoading", "calendarEmpty", ... },
  "errors":    { "loadSettings", "saveSettings", "resetSettings", "loadDeadlines" }
}
```

> **约定**：`zh.json` 直接以 UTF-8 编码存储中文字符（不使用 `\uXXXX` 转义），
> 以保证 Git diff 可读性和 IDE 搜索可用性。`check_language.py` 仅扫描
> `.py`、`.ts`、`.vue` 文件，JSON 文件不受限制。

---

## 组件使用方式

所有组件通过 **Composition API** 使用 `useI18n()`：

```vue
<script setup lang="ts">
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
</script>

<template>
  <button>{{ t('common.save') }}</button>
  <p>{{ t('chat.trace.completed', { count: steps.length }) }}</p>
</template>
```

带插值参数时，在语言包中用 `{param}` 占位：

```json
{ "completed": "ReAct Thought Process ({count} steps)" }
```

---

## 语言切换与持久化

`stores/settings.ts` 中的 `setLocale()` / `getLocale()` 负责切换语言：

```ts
function setLocale(locale: SupportedLocale): void {
  i18n.global.locale.value = locale          // 即时生效（响应式）
  localStorage.setItem(LOCALE_STORAGE_KEY, locale)  // 持久化
}

function getLocale(): SupportedLocale {
  return i18n.global.locale.value as SupportedLocale
}
```

用户在 **Settings → Language** 面板选择语言，`LanguageSettings.vue` 调用
`settingsStore.setLocale()` 即时切换全局语言，无需刷新页面。

---

## Widget 标题国际化

`widgets/index.ts` 使用 i18n key 映射替代直接字符串：

```ts
export const WIDGET_TITLE_I18N_KEYS: Record<WidgetType, string> = {
  [WIDGET_TYPES.CALENDAR]: 'widgets.calendar',
  [WIDGET_TYPES.DOCUMENT]: 'widgets.document',
  // ...
}

export interface SelectableWidget {
  type: WidgetType
  titleKey: string   // i18n key，由 WorkspacePanel 通过 t(titleKey) 解析
}
```

---

## 开发规范核心要点

详见 [i18n 开发规范](../devs/zh-CN_i18n.md)。
