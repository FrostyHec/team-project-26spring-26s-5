<script setup lang="ts">
import { ref, computed, watch, toRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { Eye, EyeOff, Save, CheckCircle, RotateCcw } from 'lucide-vue-next'
import { useSettingsStore } from '@/stores/settings'
import SettingsErrorDialog from './SettingsErrorDialog.vue'
import { useSettingsErrorDialog } from './useSettingsErrorDialog'

const { t } = useI18n()
const settingsStore = useSettingsStore()
const errorDialog = useSettingsErrorDialog(toRef(settingsStore, 'error'), {
  defaultSummary: () => t('settings.saveErrorSummary'),
})
const {
  visible: errorDialogVisible,
  summary: errorDialogSummary,
  hint: errorDialogHint,
  items: errorDialogItems,
  close: closeErrorDialog,
} = errorDialog

// ---------- Form state ----------

const casAccount = ref('')
const casPassword = ref('')
const showCasPassword = ref(false)

// Track whether we're editing the password (empty = not editing -> leave unchanged)
const isEditingCasPassword = ref(false)

// ---------- Computed ----------

const casPasswordIsSet = computed(() => settingsStore.profile?.cas_password_is_set ?? false)

const casPasswordPlaceholder = computed(() =>
  casPasswordIsSet.value && !isEditingCasPassword.value
    ? t('settings.cas.passwordPlaceholderSet')
    : t('settings.cas.passwordPlaceholderEmpty'),
)

// ---------- Lifecycle ----------

// When profile loads, populate account field
watch(
  () => settingsStore.profile,
  (profile) => {
    if (profile) {
      casAccount.value = profile.cas_account
    }
  },
  { immediate: true },
)

// ---------- Methods ----------

function onPasswordFocus(): void {
  isEditingCasPassword.value = true
}

async function handleSave(): Promise<void> {
  await settingsStore.saveProfile({
    cas_account: casAccount.value || null,
    cas_password: isEditingCasPassword.value && casPassword.value ? casPassword.value : null,
  })
  if (!settingsStore.error) {
    // Reset password field after successful save
    casPassword.value = ''
    isEditingCasPassword.value = false
  }
}

async function handleReset(): Promise<void> {
  await settingsStore.saveProfile({
    cas_account: '',
    cas_password: '',
  })
  if (!settingsStore.error) {
    casAccount.value = ''
    casPassword.value = ''
    isEditingCasPassword.value = false
    showCasPassword.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-base font-semibold text-gray-900 mb-1">{{ t('settings.cas.title') }}</h2>
      <p class="text-sm text-gray-500">{{ t('settings.cas.description') }}</p>
    </div>

    <div class="space-y-4">
      <!-- CAS Account -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1" for="cas-account">
          {{ t('settings.cas.accountLabel') }}
        </label>
        <input
          id="cas-account"
          v-model="casAccount"
          type="text"
          autocomplete="username"
          :placeholder="t('settings.cas.accountPlaceholder')"
          class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
        />
      </div>

      <!-- CAS Password -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1" for="cas-password">
          {{ t('settings.cas.passwordLabel') }}
        </label>
        <div class="relative">
          <input
            id="cas-password"
            v-model="casPassword"
            :type="showCasPassword ? 'text' : 'password'"
            autocomplete="current-password"
            :placeholder="casPasswordPlaceholder"
            class="w-full px-3 py-2 pr-10 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
            @focus="onPasswordFocus"
          />
          <button
            type="button"
            class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
            :title="
              showCasPassword ? t('settings.cas.hidePassword') : t('settings.cas.showPassword')
            "
            @click="showCasPassword = !showCasPassword"
          >
            <EyeOff v-if="showCasPassword" class="w-4 h-4" />
            <Eye v-else class="w-4 h-4" />
          </button>
        </div>
        <p
          v-if="casPasswordIsSet && !isEditingCasPassword"
          class="mt-1 text-xs text-green-600 flex items-center gap-1"
        >
          <CheckCircle class="w-3.5 h-3.5" />
          {{ t('settings.cas.passwordConfigured') }}
        </p>
      </div>
    </div>

    <!-- Security note -->
    <div class="rounded-lg bg-blue-50 border border-blue-100 px-4 py-3 text-xs text-blue-700">
      <strong>{{ t('settings.cas.securityNote') }}</strong>
      {{ t('settings.cas.securityDescription') }}
    </div>

    <!-- Save + Reset buttons -->
    <div class="flex items-center gap-3">
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

      <p v-if="settingsStore.successMessage" class="text-sm text-green-600 flex items-center gap-1">
        <CheckCircle class="w-4 h-4" />
        {{ settingsStore.successMessage }}
      </p>
    </div>

    <SettingsErrorDialog
      :visible="errorDialogVisible"
      :title="t('settings.saveErrorTitle')"
      :summary="errorDialogSummary"
      :hint="errorDialogHint"
      :items="errorDialogItems"
      @close="closeErrorDialog"
    />
  </div>
</template>
