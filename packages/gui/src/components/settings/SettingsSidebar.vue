<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useSettingsStore } from '@/stores/settings'
import {
  SETTINGS_SECTION_LIST,
  SETTINGS_SECTION_I18N_KEYS,
  type SettingsSection,
} from '@/stores/settingsConstants'

const { t } = useI18n()
const settingsStore = useSettingsStore()

function handleSelect(section: SettingsSection): void {
  settingsStore.setActiveSection(section)
}
</script>

<template>
  <nav class="flex flex-col gap-1 py-2">
    <button
      v-for="section in SETTINGS_SECTION_LIST"
      :key="section"
      type="button"
      class="w-full text-left px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150"
      :class="
        settingsStore.activeSection === section
          ? 'bg-blue-50 text-blue-700 border border-blue-100'
          : 'text-gray-600 hover:bg-gray-100 border border-transparent'
      "
      @click="handleSelect(section)"
    >
      {{ t(SETTINGS_SECTION_I18N_KEYS[section]) }}
    </button>
  </nav>
</template>
