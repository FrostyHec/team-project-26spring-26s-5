/**
 * Settings-related constants.
 *
 * ``CAS_SERVICE``, ``EMAIL_SERVICE``, and ``EXTENSION_SERVICE`` match the
 * backend ``SettingsCategory`` StrEnum values.  ``LANGUAGE`` is a
 * frontend-only UI section with no backend counterpart.
 *
 * Using ``as const`` objects (rather than TS enums) maintains consistency
 * with the existing chatConstants pattern and allows easy runtime iteration.
 *
 * Human-readable labels are provided via Vue I18n (see ``src/i18n/``).
 */

/** Settings section identifiers.
 *
 * Note: ``LANGUAGE`` is UI-only and does not correspond to a backend
 * ``SettingsCategory`` value.
 */
export const SETTINGS_SECTIONS = {
  CAS_SERVICE: 'cas_service',
  EMAIL_SERVICE: 'email_service',
  EXTENSION_SERVICE: 'extension_service',
  LANGUAGE: 'language',
} as const

export type SettingsSection = (typeof SETTINGS_SECTIONS)[keyof typeof SETTINGS_SECTIONS]

/**
 * I18n message keys for each settings section label.
 * Components use ``$t(SETTINGS_SECTION_I18N_KEYS[section])`` to render
 * the localised section name.
 */
export const SETTINGS_SECTION_I18N_KEYS: Record<SettingsSection, string> = {
  [SETTINGS_SECTIONS.CAS_SERVICE]: 'settings.sections.casService',
  [SETTINGS_SECTIONS.EMAIL_SERVICE]: 'settings.sections.emailService',
  [SETTINGS_SECTIONS.EXTENSION_SERVICE]: 'settings.sections.extensionService',
  [SETTINGS_SECTIONS.LANGUAGE]: 'settings.sections.language',
}

/** Ordered list of all settings sections for navigation. */
export const SETTINGS_SECTION_LIST: SettingsSection[] = [
  SETTINGS_SECTIONS.CAS_SERVICE,
  SETTINGS_SECTIONS.EMAIL_SERVICE,
  SETTINGS_SECTIONS.EXTENSION_SERVICE,
  SETTINGS_SECTIONS.LANGUAGE,
]

/** Duration in milliseconds before the success message auto-dismisses. */
export const SUCCESS_MESSAGE_TIMEOUT_MS = 3_000
