/**
 * Vue I18n configuration.
 *
 * Sets up internationalisation with English as the default locale and
 * Chinese (Simplified) as the alternative.  The active locale is persisted
 * to ``localStorage`` so the user's preference survives page reloads.
 */

import { createI18n } from 'vue-i18n'
import en from './locales/en.json'
import zh from './locales/zh.json'

/** localStorage key used to persist the user's locale preference. */
export const LOCALE_STORAGE_KEY = 'app-locale'

/** Supported locale identifiers. */
export const SUPPORTED_LOCALES = {
  EN: 'en',
  ZH: 'zh',
} as const

export type SupportedLocale = (typeof SUPPORTED_LOCALES)[keyof typeof SUPPORTED_LOCALES]

/** Ordered list for UI iteration. */
export const SUPPORTED_LOCALE_LIST: SupportedLocale[] = [SUPPORTED_LOCALES.EN, SUPPORTED_LOCALES.ZH]

/** Descriptive entry for the language selector UI. */
export interface LocaleEntry {
  code: SupportedLocale
  /** Vue I18n message key for the human-readable locale name. */
  labelKey: string
}

/** Locale entries with i18n label keys for the selector UI. */
export const LOCALE_ENTRIES: LocaleEntry[] = [
  { code: SUPPORTED_LOCALES.EN, labelKey: 'settings.language.english' },
  { code: SUPPORTED_LOCALES.ZH, labelKey: 'settings.language.chinese' },
]

/** Resolve the initial locale from localStorage (fallback: English). */
function getPersistedLocale(): SupportedLocale {
  const stored = localStorage.getItem(LOCALE_STORAGE_KEY)
  if (stored === SUPPORTED_LOCALES.ZH) return SUPPORTED_LOCALES.ZH
  return SUPPORTED_LOCALES.EN
}

const i18n = createI18n({
  legacy: false,
  locale: getPersistedLocale(),
  fallbackLocale: SUPPORTED_LOCALES.EN,
  messages: { en, zh },
})

export default i18n
