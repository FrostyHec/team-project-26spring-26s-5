<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const props = withDefaults(
  defineProps<{
    visible: boolean
    title: string
    summary?: string
    hint?: string
    items: string[]
  }>(),
  {
    summary: '',
    hint: '',
  },
)

const emit = defineEmits<{
  close: []
}>()

const { t } = useI18n()
</script>

<template>
  <div
    v-if="props.visible"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
    @click.self="emit('close')"
  >
    <div class="mx-4 w-full max-w-lg rounded-lg bg-white shadow-xl">
      <div class="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <h3 class="text-sm font-semibold text-gray-700">{{ props.title }}</h3>
        <button class="text-gray-400 hover:text-gray-600" @click="emit('close')">✕</button>
      </div>
      <div class="px-4 py-4 space-y-3">
        <p v-if="props.summary" class="text-sm text-gray-700">
          {{ props.summary }}
        </p>
        <ul v-if="props.items.length > 0" class="space-y-2 rounded-lg bg-red-50 px-3 py-3">
          <li v-for="item in props.items" :key="item" class="text-sm leading-6 text-red-700">
            {{ item }}
          </li>
        </ul>
        <p v-if="props.hint" class="text-xs leading-5 text-gray-500">
          {{ props.hint }}
        </p>
      </div>
      <div class="flex justify-end border-t border-gray-200 px-4 py-3">
        <button
          class="rounded-lg bg-red-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-red-700"
          @click="emit('close')"
        >
          {{ t('common.close') }}
        </button>
      </div>
    </div>
  </div>
</template>
