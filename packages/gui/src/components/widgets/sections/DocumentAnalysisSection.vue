<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { FileText, BookOpen, Lightbulb, AlertCircle, Hash } from 'lucide-vue-next'

const { t } = useI18n()

const props = defineProps<{
  summary: string
  keyPoints: string[]
  difficultConcepts: string[]
  suggestedTopics: string[]
  docType: string
  originalLength: number
}>()

const formattedLength = computed(() => {
  const len = props.originalLength
  if (len < 1000) return `${len} chars`
  if (len < 10000) return `${(len / 1000).toFixed(1)}K chars`
  return `${(len / 1000).toFixed(0)}K chars`
})
</script>

<template>
  <div class="p-4 space-y-6 overflow-y-auto max-h-full">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <FileText class="w-5 h-5 text-purple-600" />
        <h3 class="font-semibold text-gray-800">{{ t('course.documentAnalysis') }}</h3>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded uppercase">
          {{ docType }}
        </span>
        <span class="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">
          {{ formattedLength }}
        </span>
      </div>
    </div>

    <!-- Summary -->
    <div v-if="summary">
      <h4 class="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
        <BookOpen class="w-4 h-4 text-purple-500" />
        {{ t('course.summary') }}
      </h4>
      <div class="bg-purple-50 border-l-3 border-purple-400 rounded-r-lg p-4 text-sm text-gray-700">
        <p class="whitespace-pre-wrap">{{ summary }}</p>
      </div>
    </div>

    <!-- Key Points -->
    <div v-if="keyPoints.length > 0">
      <h4 class="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
        <Lightbulb class="w-4 h-4 text-yellow-500" />
        {{ t('course.keyPoints') }}
      </h4>
      <div class="space-y-2">
        <div
          v-for="(point, index) in keyPoints"
          :key="index"
          class="flex gap-3 p-3 bg-white border border-gray-200 rounded-lg text-sm"
        >
          <span
            class="flex-shrink-0 w-6 h-6 flex items-center justify-center bg-yellow-100 text-yellow-700 text-xs font-medium rounded-full"
          >
            {{ index + 1 }}
          </span>
          <p class="text-gray-700">{{ point }}</p>
        </div>
      </div>
    </div>

    <!-- Difficult Concepts -->
    <div v-if="difficultConcepts.length > 0">
      <h4 class="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
        <AlertCircle class="w-4 h-4 text-orange-500" />
        {{ t('course.conceptsToReview') }}
      </h4>
      <div class="flex flex-wrap gap-2">
        <span
          v-for="(concept, index) in difficultConcepts"
          :key="index"
          class="px-3 py-1 bg-orange-50 text-orange-700 text-sm rounded-full border border-orange-200"
        >
          {{ concept }}
        </span>
      </div>
    </div>

    <!-- Suggested Topics -->
    <div v-if="suggestedTopics.length > 0">
      <h4 class="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
        <Hash class="w-4 h-4 text-green-500" />
        {{ t('course.suggestedStudyTopics') }}
      </h4>
      <div class="flex flex-wrap gap-2">
        <span
          v-for="(topic, index) in suggestedTopics"
          :key="index"
          class="px-3 py-1 bg-green-50 text-green-700 text-sm rounded-full border border-green-200"
        >
          {{ topic }}
        </span>
      </div>
    </div>
  </div>
</template>
