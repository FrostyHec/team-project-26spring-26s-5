import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSettingsStore } from '../settings'
import { SETTINGS_SECTIONS } from '../settingsConstants'

// Mock vue-i18n so useI18n() returns a simple t() that echoes the key
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
  createI18n: () => ({}),
}))

// Mock the i18n module
vi.mock('@/i18n', () => {
  const localeRef = { value: 'en' }
  return {
    default: { global: { locale: localeRef } },
    LOCALE_STORAGE_KEY: 'app-locale',
    SUPPORTED_LOCALES: { EN: 'en', ZH: 'zh' },
    SUPPORTED_LOCALE_LIST: ['en', 'zh'],
  }
})

// Mock the API module
vi.mock('@/api/settings', () => ({
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  resetSettings: vi.fn(),
}))

import { getSettings, updateSettings, resetSettings } from '@/api/settings'

const mockGetSettings = vi.mocked(getSettings)
const mockUpdateSettings = vi.mocked(updateSettings)
const mockResetSettings = vi.mocked(resetSettings)

const MOCK_PROFILE = {
  cas_account: 'testuser',
  cas_password_is_set: true,
  email_account: 'test@mail.sustech.edu.cn',
  email_password_is_set: false,
}

const EMPTY_PROFILE = {
  cas_account: '',
  cas_password_is_set: false,
  email_account: '',
  email_password_is_set: false,
}

describe('useSettingsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    const mockLocalStorage = {
      setItem: vi.fn(),
      getItem: vi.fn(),
      removeItem: vi.fn(),
    }
    vi.stubGlobal('localStorage', mockLocalStorage)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('initializes with correct default state', () => {
    const store = useSettingsStore()
    expect(store.isOpen).toBe(false)
    expect(store.activeSection).toBe(SETTINGS_SECTIONS.CAS_SERVICE)
    expect(store.profile).toBeNull()
    expect(store.isLoading).toBe(false)
    expect(store.isSaving).toBe(false)
    expect(store.error).toBeNull()
    expect(store.successMessage).toBeNull()
  })

  describe('openSettings', () => {
    it('sets isOpen to true', async () => {
      mockGetSettings.mockResolvedValue(EMPTY_PROFILE)
      const store = useSettingsStore()
      await store.openSettings()
      expect(store.isOpen).toBe(true)
    })

    it('resets activeSection to CAS_SERVICE', async () => {
      mockGetSettings.mockResolvedValue(EMPTY_PROFILE)
      const store = useSettingsStore()
      store.setActiveSection(SETTINGS_SECTIONS.EMAIL_SERVICE)
      await store.openSettings()
      expect(store.activeSection).toBe(SETTINGS_SECTIONS.CAS_SERVICE)
    })

    it('loads the profile', async () => {
      mockGetSettings.mockResolvedValue(MOCK_PROFILE)
      const store = useSettingsStore()
      await store.openSettings()
      expect(store.profile).toEqual(MOCK_PROFILE)
      expect(mockGetSettings).toHaveBeenCalledTimes(1)
    })
  })

  describe('closeSettings', () => {
    it('sets isOpen to false', () => {
      const store = useSettingsStore()
      store.isOpen = true
      store.closeSettings()
      expect(store.isOpen).toBe(false)
    })

    it('clears error and successMessage', () => {
      const store = useSettingsStore()
      store.error = 'some error'
      store.successMessage = 'saved!'
      store.closeSettings()
      expect(store.error).toBeNull()
      expect(store.successMessage).toBeNull()
    })
  })

  describe('setActiveSection', () => {
    it('changes the active section', () => {
      const store = useSettingsStore()
      store.setActiveSection(SETTINGS_SECTIONS.EMAIL_SERVICE)
      expect(store.activeSection).toBe(SETTINGS_SECTIONS.EMAIL_SERVICE)
    })

    it('clears error and successMessage', () => {
      const store = useSettingsStore()
      store.error = 'err'
      store.successMessage = 'ok'
      store.setActiveSection(SETTINGS_SECTIONS.EXTENSION_SERVICE)
      expect(store.error).toBeNull()
      expect(store.successMessage).toBeNull()
    })
  })

  describe('loadProfile', () => {
    it('sets profile on success', async () => {
      mockGetSettings.mockResolvedValue(MOCK_PROFILE)
      const store = useSettingsStore()
      await store.loadProfile()
      expect(store.profile).toEqual(MOCK_PROFILE)
      expect(store.isLoading).toBe(false)
    })

    it('sets error on failure', async () => {
      mockGetSettings.mockRejectedValue(new Error('Network error'))
      const store = useSettingsStore()
      await store.loadProfile()
      expect(store.error).toBe('errors.loadSettings')
      expect(store.profile).toBeNull()
    })

    it('sets isLoading to false after completion', async () => {
      mockGetSettings.mockResolvedValue(EMPTY_PROFILE)
      const store = useSettingsStore()
      await store.loadProfile()
      expect(store.isLoading).toBe(false)
    })
  })

  describe('saveProfile', () => {
    it('calls updateSettings with correct request', async () => {
      mockUpdateSettings.mockResolvedValue(MOCK_PROFILE)
      const store = useSettingsStore()

      await store.saveProfile({ cas_account: 'newuser', cas_password: 'pw' })

      expect(mockUpdateSettings).toHaveBeenCalledWith({
        cas_account: 'newuser',
        cas_password: 'pw',
      })
    })

    it('updates profile on success', async () => {
      mockUpdateSettings.mockResolvedValue(MOCK_PROFILE)
      const store = useSettingsStore()
      await store.saveProfile({ cas_account: 'user' })
      expect(store.profile).toEqual(MOCK_PROFILE)
    })

    it('sets successMessage on success', async () => {
      mockUpdateSettings.mockResolvedValue(MOCK_PROFILE)
      const store = useSettingsStore()
      await store.saveProfile({ cas_account: 'user' })
      expect(store.successMessage).toBe('settings.settingsSaved')
    })

    it('clears successMessage after 3 seconds', async () => {
      vi.useFakeTimers()
      mockUpdateSettings.mockResolvedValue(MOCK_PROFILE)
      const store = useSettingsStore()
      await store.saveProfile({ cas_account: 'user' })
      expect(store.successMessage).toBe('settings.settingsSaved')
      vi.advanceTimersByTime(3000)
      expect(store.successMessage).toBeNull()
    })

    it('sets error on failure', async () => {
      mockUpdateSettings.mockRejectedValue(new Error('Server error'))
      const store = useSettingsStore()
      await store.saveProfile({ cas_account: 'user' })
      expect(store.error).toBe('errors.saveSettings')
      expect(store.successMessage).toBeNull()
    })

    it('sets isSaving to false after completion', async () => {
      mockUpdateSettings.mockResolvedValue(EMPTY_PROFILE)
      const store = useSettingsStore()
      await store.saveProfile({})
      expect(store.isSaving).toBe(false)
    })

    it('clears previous error before new save', async () => {
      const store = useSettingsStore()
      store.error = 'previous error'
      mockUpdateSettings.mockResolvedValue(EMPTY_PROFILE)
      await store.saveProfile({})
      expect(store.error).toBeNull()
    })
  })

  describe('resetProfile', () => {
    it('calls resetSettings API', async () => {
      mockResetSettings.mockResolvedValue(EMPTY_PROFILE)
      const store = useSettingsStore()
      await store.resetProfile()
      expect(mockResetSettings).toHaveBeenCalledTimes(1)
    })

    it('updates profile with empty values on success', async () => {
      mockResetSettings.mockResolvedValue(EMPTY_PROFILE)
      const store = useSettingsStore()
      store.profile = MOCK_PROFILE
      await store.resetProfile()
      expect(store.profile).toEqual(EMPTY_PROFILE)
    })

    it('sets successMessage on success', async () => {
      mockResetSettings.mockResolvedValue(EMPTY_PROFILE)
      const store = useSettingsStore()
      await store.resetProfile()
      expect(store.successMessage).toBe('settings.settingsReset')
    })

    it('sets error on failure', async () => {
      mockResetSettings.mockRejectedValue(new Error('Reset failed'))
      const store = useSettingsStore()
      await store.resetProfile()
      expect(store.error).toBe('errors.resetSettings')
    })

    it('sets isResetting to false after completion', async () => {
      mockResetSettings.mockResolvedValue(EMPTY_PROFILE)
      const store = useSettingsStore()
      await store.resetProfile()
      expect(store.isResetting).toBe(false)
    })
  })

  describe('locale management', () => {
    it('getLocale returns default en', () => {
      const store = useSettingsStore()
      expect(store.getLocale()).toBe('en')
    })

    it('setLocale updates localStorage', () => {
      const store = useSettingsStore()
      store.setLocale('zh')
      expect(localStorage.setItem).toHaveBeenCalledWith('app-locale', 'zh')
    })
  })
})
