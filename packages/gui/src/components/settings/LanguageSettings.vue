<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Globe, CheckCircle } from 'lucide-vue-next'
import { useSettingsStore } from '@/stores/settings'
import { LOCALE_ENTRIES, type SupportedLocale } from '@/i18n'

const { t } = useI18n()
const settingsStore = useSettingsStore()

const currentLocale = ref<SupportedLocale>(settingsStore.getLocale())

watch(currentLocale, (newLocale) => {
  settingsStore.setLocale(newLocale)
})
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-base font-semibold text-gray-900 mb-1">{{ t('settings.language.title') }}</h2>
      <p class="text-sm text-gray-500">{{ t('settings.language.description') }}</p>
    </div>

    <div class="space-y-2">
      <label
        v-for="loc in LOCALE_ENTRIES"
        :key="loc.code"
        class="flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors"
        :class="
          currentLocale === loc.code
            ? 'border-blue-300 bg-blue-50'
            : 'border-gray-200 hover:bg-gray-50'
        "
      >
        <input
          v-model="currentLocale"
          type="radio"
          name="locale"
          :value="loc.code"
          class="sr-only"
        />
        <Globe
          class="w-5 h-5 flex-shrink-0"
          :class="currentLocale === loc.code ? 'text-blue-600' : 'text-gray-400'"
        />
        <span
          class="text-sm font-medium flex-1"
          :class="currentLocale === loc.code ? 'text-blue-700' : 'text-gray-700'"
        >
          {{ t(loc.labelKey) }}
        </span>
        <CheckCircle
          v-if="currentLocale === loc.code"
          class="w-4 h-4 text-blue-600 flex-shrink-0"
        />
      </label>
    </div>
  </div>
</template>
