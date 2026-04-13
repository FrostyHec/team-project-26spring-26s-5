<script setup lang="ts">
// Extension service settings — placeholder for future integrations.
// No form fields at this stage; display a "coming soon" message.
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-base font-semibold text-gray-900 mb-1">
        {{ t('settings.extension.title') }}
      </h2>
      <p class="text-sm text-gray-500">{{ t('settings.extension.description') }}</p>
    </div>

    <div
      class="flex flex-col items-center justify-center py-16 text-center rounded-xl border-2 border-dashed border-gray-200 bg-gray-50"
    >
      <div class="w-14 h-14 rounded-full bg-blue-50 flex items-center justify-center mb-4">
        <span class="text-2xl" role="img" aria-label="coming soon">🚀</span>
      </div>
      <p class="text-base font-semibold text-gray-700 mb-1">
        {{ t('settings.extension.comingSoon') }}
      </p>
      <p class="text-sm text-gray-400">{{ t('settings.extension.comingSoonDescription') }}</p>
    </div>
  </div>
</template>
