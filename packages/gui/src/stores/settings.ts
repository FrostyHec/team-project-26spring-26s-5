import { ref } from 'vue'
import { defineStore } from 'pinia'
import { useI18n } from 'vue-i18n'
import { getSettings, updateSettings, resetSettings } from '@/api/settings'
import type { SettingsResponse, UpdateSettingsRequest } from '@/api/settings'
import {
  SETTINGS_SECTIONS,
  SUCCESS_MESSAGE_TIMEOUT_MS,
  type SettingsSection,
} from './settingsConstants'
import { LOCALE_STORAGE_KEY, type SupportedLocale } from '@/i18n'
import i18n from '@/i18n'

// Re-export constants so consumers can import from '@/stores/settings' if preferred
export {
  SETTINGS_SECTIONS,
  SETTINGS_SECTION_I18N_KEYS,
  SETTINGS_SECTION_LIST,
} from './settingsConstants'
export type { SettingsSection }

export const useSettingsStore = defineStore('settings', () => {
  const { t } = useI18n()

  // ---------- State ----------

  /** Whether the settings panel is currently open. */
  const isOpen = ref(false)

  /** The currently selected section in the settings navigation sidebar. */
  const activeSection = ref<SettingsSection>(SETTINGS_SECTIONS.CAS_SERVICE)

  /** The loaded settings profile from the backend. */
  const profile = ref<SettingsResponse | null>(null)

  /** True while fetching settings from the backend. */
  const isLoading = ref(false)

  /** True while saving settings to the backend. */
  const isSaving = ref(false)

  /** True while resetting settings. */
  const isResetting = ref(false)

  /** Error message from the last failed operation, or null. */
  const error = ref<string | null>(null)

  /** Success message from the last successful save, or null. */
  const successMessage = ref<string | null>(null)

  // ---------- Actions ----------

  /** Open the settings panel and load the current profile. */
  async function openSettings(): Promise<void> {
    isOpen.value = true
    activeSection.value = SETTINGS_SECTIONS.CAS_SERVICE
    await loadProfile()
  }

  /** Close the settings panel and clear transient state. */
  function closeSettings(): void {
    isOpen.value = false
    error.value = null
    successMessage.value = null
  }

  /** Set the active settings section. */
  function setActiveSection(section: SettingsSection): void {
    activeSection.value = section
    error.value = null
    successMessage.value = null
  }

  /** Fetch the current settings profile from the backend. */
  async function loadProfile(): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      profile.value = await getSettings()
    } catch {
      error.value = t('errors.loadSettings')
    } finally {
      isLoading.value = false
    }
  }

  /** Save a partial settings update to the backend.
   *
   * @param request - Partial update with plaintext credentials.
   */
  async function saveProfile(request: UpdateSettingsRequest): Promise<void> {
    isSaving.value = true
    error.value = null
    successMessage.value = null
    try {
      profile.value = await updateSettings(request)
      successMessage.value = t('settings.settingsSaved')
      // Clear success message after timeout
      setTimeout(() => {
        successMessage.value = null
      }, SUCCESS_MESSAGE_TIMEOUT_MS)
    } catch {
      error.value = t('errors.saveSettings')
    } finally {
      isSaving.value = false
    }
  }

  /** Reset all settings to their initial (empty) state. */
  async function resetProfile(): Promise<void> {
    isResetting.value = true
    error.value = null
    successMessage.value = null
    try {
      profile.value = await resetSettings()
      successMessage.value = t('settings.settingsReset')
      setTimeout(() => {
        successMessage.value = null
      }, SUCCESS_MESSAGE_TIMEOUT_MS)
    } catch {
      error.value = t('errors.resetSettings')
    } finally {
      isResetting.value = false
    }
  }

  /** Switch the application locale and persist the choice. */
  function setLocale(locale: SupportedLocale): void {
    i18n.global.locale.value = locale
    localStorage.setItem(LOCALE_STORAGE_KEY, locale)
  }

  /** Get the current locale. */
  function getLocale(): SupportedLocale {
    return i18n.global.locale.value as SupportedLocale
  }

  return {
    // State
    isOpen,
    activeSection,
    profile,
    isLoading,
    isSaving,
    isResetting,
    error,
    successMessage,
    // Actions
    openSettings,
    closeSettings,
    setActiveSection,
    loadProfile,
    saveProfile,
    resetProfile,
    setLocale,
    getLocale,
  }
})
