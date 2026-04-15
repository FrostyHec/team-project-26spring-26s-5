<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Eye, EyeOff, Save, CheckCircle, RotateCcw, Loader2, Wifi, Trash2 } from 'lucide-vue-next'
import { useSettingsStore } from '@/stores/settings'
import { useEmailStore } from '@/stores/email'

const { t } = useI18n()
const settingsStore = useSettingsStore()
const emailStore = useEmailStore()

// Error modal state
const showErrorModal = ref(false)
watch(
  () => settingsStore.error,
  (err) => {
    if (err) showErrorModal.value = true
  },
)
function closeErrorModal() {
  showErrorModal.value = false
  settingsStore.error = null
}

// ---------- Form state ----------

const emailAccount = ref('')
const emailPassword = ref('')
const showEmailPassword = ref(false)
const isEditingEmailPassword = ref(false)

// Email-specific settings
const fetchDays = ref(30)
const autoSync = ref(false)

// Test connection state
const testingConnection = ref(false)
const connectionResult = ref<{ success: boolean; message: string } | null>(null)

// Clear cache state
const clearingCache = ref(false)
const cacheResult = ref<string | null>(null)

// ---------- Computed ----------

const emailPasswordIsSet = computed(() => settingsStore.profile?.email_password_is_set ?? false)

const emailPasswordPlaceholder = computed(() =>
  emailPasswordIsSet.value && !isEditingEmailPassword.value
    ? t('settings.email.passwordPlaceholderSet')
    : t('settings.email.passwordPlaceholderEmpty'),
)

// ---------- Lifecycle ----------

watch(
  () => settingsStore.profile,
  (profile) => {
    if (profile) {
      emailAccount.value = profile.email_account
    }
  },
  { immediate: true },
)

onMounted(async () => {
  try {
    const settings = await emailStore.fetchSettings()
    fetchDays.value = settings.email_fetch_days
    autoSync.value = settings.auto_sync
  } catch {
    // Use defaults if fetch fails
  }
})

// ---------- Methods ----------

function onPasswordFocus(): void {
  isEditingEmailPassword.value = true
}

async function handleSave(): Promise<void> {
  await settingsStore.saveProfile({
    email_account: emailAccount.value || null,
    email_password:
      isEditingEmailPassword.value && emailPassword.value ? emailPassword.value : null,
  })
  if (!settingsStore.error) {
    emailPassword.value = ''
    isEditingEmailPassword.value = false
  }

  // Also save email-specific settings
  try {
    await emailStore.updateSettings({
      email_fetch_days: fetchDays.value,
      auto_sync: autoSync.value,
    })
  } catch (e: unknown) {
    settingsStore.error = e instanceof Error ? e.message : String(e)
  }
}

async function handleReset(): Promise<void> {
  await settingsStore.saveProfile({
    email_account: '',
    email_password: '',
  })
  if (!settingsStore.error) {
    emailAccount.value = ''
    emailPassword.value = ''
    isEditingEmailPassword.value = false
    showEmailPassword.value = false
    fetchDays.value = 30
    autoSync.value = false
  }
}

async function handleTestConnection(): Promise<void> {
  testingConnection.value = true
  connectionResult.value = null
  try {
    const result = await emailStore.testConnection()
    connectionResult.value = {
      success: result.success,
      message: result.message,
    }
  } catch (e: unknown) {
    connectionResult.value = {
      success: false,
      message: e instanceof Error ? e.message : String(e),
    }
  } finally {
    testingConnection.value = false
  }
}

async function handleClearCache(): Promise<void> {
  clearingCache.value = true
  cacheResult.value = null
  try {
    const result = await emailStore.clearCache()
    const sizeMB = (result.cleared_bytes / (1024 * 1024)).toFixed(2)
    cacheResult.value = t('settings.email.cacheCleared', {
      files: result.cleared_files,
      size: sizeMB,
    })
  } catch (e: unknown) {
    cacheResult.value = e instanceof Error ? e.message : String(e)
  } finally {
    clearingCache.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-base font-semibold text-gray-900 mb-1">{{ t('settings.email.title') }}</h2>
      <p class="text-sm text-gray-500">{{ t('settings.email.description') }}</p>
    </div>

    <div class="space-y-4">
      <!-- Email Account -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1" for="email-account">
          {{ t('settings.email.accountLabel') }}
        </label>
        <input
          id="email-account"
          v-model="emailAccount"
          type="email"
          autocomplete="email"
          :placeholder="t('settings.email.accountPlaceholder')"
          class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
        />
      </div>

      <!-- Email Password -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1" for="email-password">
          {{ t('settings.email.passwordLabel') }}
        </label>
        <div class="relative">
          <input
            id="email-password"
            v-model="emailPassword"
            :type="showEmailPassword ? 'text' : 'password'"
            autocomplete="current-password"
            :placeholder="emailPasswordPlaceholder"
            class="w-full px-3 py-2 pr-10 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
            @focus="onPasswordFocus"
          />
          <button
            type="button"
            class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
            :title="
              showEmailPassword
                ? t('settings.email.hidePassword')
                : t('settings.email.showPassword')
            "
            @click="showEmailPassword = !showEmailPassword"
          >
            <EyeOff v-if="showEmailPassword" class="w-4 h-4" />
            <Eye v-else class="w-4 h-4" />
          </button>
        </div>
        <p
          v-if="emailPasswordIsSet && !isEditingEmailPassword"
          class="mt-1 text-xs text-green-600 flex items-center gap-1"
        >
          <CheckCircle class="w-3.5 h-3.5" />
          {{ t('settings.email.passwordConfigured') }}
        </p>
      </div>

      <!-- Fetch Days -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1" for="email-fetch-days">
          {{ t('settings.email.fetchDaysLabel') }}
        </label>
        <div class="flex items-center gap-3">
          <input
            id="email-fetch-days"
            v-model.number="fetchDays"
            type="range"
            min="1"
            max="90"
            class="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
          />
          <span class="text-sm text-gray-600 w-16 text-right">
            {{ fetchDays }} {{ t('settings.email.days') }}
          </span>
        </div>
      </div>

      <!-- Auto Sync toggle -->
      <div class="flex items-center justify-between">
        <div>
          <label class="text-sm font-medium text-gray-700" for="email-auto-sync">
            {{ t('settings.email.autoSyncLabel') }}
          </label>
          <p class="text-xs text-gray-500">{{ t('settings.email.autoSyncDescription') }}</p>
        </div>
        <button
          id="email-auto-sync"
          type="button"
          class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
          :class="autoSync ? 'bg-blue-600' : 'bg-gray-300'"
          @click="autoSync = !autoSync"
        >
          <span
            class="inline-block h-4 w-4 rounded-full bg-white transition-transform"
            :class="autoSync ? 'translate-x-6' : 'translate-x-1'"
          />
        </button>
      </div>
    </div>

    <!-- Security note -->
    <div class="rounded-lg bg-blue-50 border border-blue-100 px-4 py-3 text-xs text-blue-700">
      <strong>{{ t('settings.email.securityNote') }}</strong>
      {{ t('settings.email.securityDescription') }}
    </div>

    <!-- Save + Reset + Test Connection + Clear Cache -->
    <div class="flex flex-wrap items-center gap-3">
      <button
        type="button"
        class="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        :disabled="settingsStore.isSaving"
        @click="handleSave"
      >
        <Save class="w-4 h-4" />
        {{ settingsStore.isSaving ? t('common.saving') : t('common.save') }}
      </button>

      <button
        type="button"
        class="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        :disabled="settingsStore.isSaving || settingsStore.isResetting"
        @click="handleReset"
      >
        <RotateCcw class="w-4 h-4" />
        {{ t('common.reset') }}
      </button>

      <button
        type="button"
        class="flex items-center gap-2 px-4 py-2 text-sm font-medium text-teal-700 bg-teal-50 rounded-lg hover:bg-teal-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        :disabled="testingConnection"
        @click="handleTestConnection"
      >
        <Loader2 v-if="testingConnection" class="w-4 h-4 animate-spin" />
        <Wifi v-else class="w-4 h-4" />
        {{ t('settings.email.testConnection') }}
      </button>

      <button
        type="button"
        class="flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-700 bg-red-50 rounded-lg hover:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        :disabled="clearingCache"
        @click="handleClearCache"
      >
        <Loader2 v-if="clearingCache" class="w-4 h-4 animate-spin" />
        <Trash2 v-else class="w-4 h-4" />
        {{ t('settings.email.clearCache') }}
      </button>
    </div>

    <!-- Error modal -->
    <div
      v-if="showErrorModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
      @click.self="showErrorModal = false"
    >
      <div class="mx-4 w-full max-w-sm rounded-lg bg-white shadow-xl">
        <div class="flex items-center justify-between border-b border-gray-200 px-4 py-3">
          <h3 class="text-sm font-semibold text-gray-700">
            {{ t('settings.saveErrorTitle') }}
          </h3>
          <button class="text-gray-400 hover:text-gray-600" @click="closeErrorModal">✕</button>
        </div>
        <div class="px-4 py-4">
          <p class="text-sm text-gray-600">{{ settingsStore.error }}</p>
        </div>
        <div class="flex justify-end border-t border-gray-200 px-4 py-3">
          <button
            class="px-4 py-1.5 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700"
            @click="closeErrorModal"
          >
            {{ t('common.close') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Feedback messages -->
    <div class="space-y-2">
      <p v-if="settingsStore.successMessage" class="text-sm text-green-600 flex items-center gap-1">
        <CheckCircle class="w-4 h-4" />
        {{ settingsStore.successMessage }}
      </p>
      <p
        v-if="connectionResult"
        class="text-sm flex items-center gap-1"
        :class="connectionResult.success ? 'text-green-600' : 'text-red-600'"
      >
        <CheckCircle v-if="connectionResult.success" class="w-4 h-4" />
        {{ connectionResult.message }}
      </p>
      <p v-if="cacheResult" class="text-sm text-blue-600">
        {{ cacheResult }}
      </p>
    </div>
  </div>
</template>
