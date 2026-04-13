<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { useI18n } from 'vue-i18n'
import { X } from 'lucide-vue-next'
import { useSettingsStore } from '@/stores/settings'
import { SETTINGS_SECTIONS, type SettingsSection } from '@/stores/settingsConstants'
import SettingsSidebar from './SettingsSidebar.vue'

const { t } = useI18n()
const settingsStore = useSettingsStore()

// Lazy-load section content components
const SECTION_COMPONENTS: Record<SettingsSection, ReturnType<typeof defineAsyncComponent>> = {
  [SETTINGS_SECTIONS.CAS_SERVICE]: defineAsyncComponent(() => import('./CasServiceSettings.vue')),
  [SETTINGS_SECTIONS.EMAIL_SERVICE]: defineAsyncComponent(
    () => import('./EmailServiceSettings.vue'),
  ),
  [SETTINGS_SECTIONS.EXTENSION_SERVICE]: defineAsyncComponent(
    () => import('./ExtensionServiceSettings.vue'),
  ),
  [SETTINGS_SECTIONS.LANGUAGE]: defineAsyncComponent(() => import('./LanguageSettings.vue')),
}

const activeSectionComponent = computed(() => SECTION_COMPONENTS[settingsStore.activeSection])
</script>

<template>
  <div class="flex flex-col h-full w-full bg-white">
    <!-- Header -->
    <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 flex-shrink-0">
      <h1 class="text-lg font-semibold text-gray-900">{{ t('settings.title') }}</h1>
      <button
        type="button"
        class="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
        :title="t('settings.closeTitle')"
        @click="settingsStore.closeSettings"
      >
        <X class="w-5 h-5" />
      </button>
    </div>

    <!-- Body: sidebar + content -->
    <div class="flex flex-1 overflow-hidden">
      <!-- Left sidebar: navigation index -->
      <aside
        class="w-48 flex-shrink-0 border-r border-gray-200 bg-gray-50 px-3 py-2 overflow-y-auto"
      >
        <SettingsSidebar />
      </aside>

      <!-- Right: section content (scrollable) -->
      <main class="flex-1 overflow-y-auto px-8 py-6">
        <!-- Loading skeleton -->
        <div v-if="settingsStore.isLoading" class="space-y-4 animate-pulse">
          <div class="h-5 w-32 bg-gray-200 rounded" />
          <div class="h-4 w-64 bg-gray-100 rounded" />
          <div class="h-10 bg-gray-100 rounded-lg" />
          <div class="h-10 bg-gray-100 rounded-lg" />
        </div>

        <!-- Section content -->
        <component :is="activeSectionComponent" v-else />
      </main>
    </div>
  </div>
</template>
