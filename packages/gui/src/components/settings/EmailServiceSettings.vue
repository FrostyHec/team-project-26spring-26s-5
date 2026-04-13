<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Eye, EyeOff, Save, CheckCircle, RotateCcw } from 'lucide-vue-next'
import { useSettingsStore } from '@/stores/settings'

const { t } = useI18n()
const settingsStore = useSettingsStore()

// ---------- Form state ----------

const emailAccount = ref('')
const emailPassword = ref('')
const showEmailPassword = ref(false)
const isEditingEmailPassword = ref(false)

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
    </div>

    <!-- Security note -->
    <div class="rounded-lg bg-blue-50 border border-blue-100 px-4 py-3 text-xs text-blue-700">
      <strong>{{ t('settings.email.securityNote') }}</strong>
      {{ t('settings.email.securityDescription') }}
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
      <p v-if="settingsStore.error" class="text-sm text-red-600">
        {{ settingsStore.error }}
      </p>
    </div>
  </div>
</template>
