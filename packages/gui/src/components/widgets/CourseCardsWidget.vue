<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { BookOpen, HelpCircle, FileText, ChevronDown } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import CourseSection from './sections/CourseSection.vue'
import QuizSection from './sections/QuizSection.vue'
import DocumentAnalysisSection from './sections/DocumentAnalysisSection.vue'
import type { CourseInfo, QuizQuestion } from './types'

const { t } = useI18n()

// ========== Props ==========
const props = defineProps<{
  data: Record<string, unknown>
}>()

// ========== Section key type ==========
type SectionKey = 'courses' | 'questions' | 'analysis'

interface Section {
  key: SectionKey
  labelKey: string
  color: string
  icon: typeof BookOpen
  count: number
}

// ========== Computed data ==========
const courses = computed<CourseInfo[]>(() =>
  Array.isArray(props.data.courses) ? (props.data.courses as CourseInfo[]) : [],
)

const title = computed(() => (props.data.title as string) || t('quiz.defaultTitle'))
const questions = computed<QuizQuestion[]>(() => {
  const q = props.data.questions
  return Array.isArray(q) ? (q as QuizQuestion[]) : []
})
const quizType = computed(() => {
  const meta = props.data.metadata as Record<string, unknown> | undefined
  return (meta?.quiz_type as string) || 'mixed'
})
const quizDifficulty = computed(() => {
  const d = props.data.difficulty
  return d === 'easy' || d === 'medium' || d === 'hard' ? d : undefined
})

const summary = computed(() => (props.data.summary as string) || '')
const keyPoints = computed(() =>
  Array.isArray(props.data.key_points) ? (props.data.key_points as string[]) : [],
)
const difficultConcepts = computed(() =>
  Array.isArray(props.data.difficult_concepts) ? (props.data.difficult_concepts as string[]) : [],
)
const suggestedTopics = computed(() =>
  Array.isArray(props.data.suggested_topics) ? (props.data.suggested_topics as string[]) : [],
)
const docType = computed(() => (props.data.doc_type as string) || 'text')
const originalLength = computed(() => (props.data.original_length as number) || 0)

// ========== Accordion logic ==========
const expandedSections = ref<Set<SectionKey>>(new Set())

const availableSections = computed<Section[]>(() => {
  const sections: Section[] = []
  if (courses.value.length > 0) {
    sections.push({
      key: 'courses',
      labelKey: 'quiz.courseRecommend',
      color: '#3b82f6',
      icon: BookOpen,
      count: courses.value.length,
    })
  }
  if (questions.value.length > 0) {
    sections.push({
      key: 'questions',
      labelKey: 'widgets.quiz',
      color: '#8b5cf6',
      icon: HelpCircle,
      count: questions.value.length,
    })
  }
  if (
    summary.value ||
    keyPoints.value.length > 0 ||
    difficultConcepts.value.length > 0 ||
    suggestedTopics.value.length > 0
  ) {
    sections.push({
      key: 'analysis',
      labelKey: 'quiz.documentAnalysis',
      color: '#10b981',
      icon: FileText,
      count:
        keyPoints.value.length +
        difficultConcepts.value.length +
        suggestedTopics.value.length +
        (summary.value ? 1 : 0),
    })
  }
  return sections
})

const firstSection = computed<Section | null>(() => {
  const sections = availableSections.value
  if (sections.length === 0) return null
  return sections[0] ?? null
})

/** The single section when exactly one is available — always non-null within the single-section template branch. */
const singleSection = computed<Section | undefined>(() =>
  availableSections.value.length === 1 ? availableSections.value[0] : undefined,
)

// Initialize expansion state based on number of sections
// - 1 section: auto expand
// - 3 sections: all collapsed
// - 2 sections: expand first one
//
// Only auto-expands when availableSections FIRST gains content (from empty → non-empty).
// Does NOT override user manually collapsed/expanded sections on subsequent data changes.
const hasInitializedOnce = ref(false)

const initExpansion = (sections: Section[]) => {
  const first = sections[0]
  if (!first) return
  const count = sections.length
  if (count === 1) {
    expandedSections.value.add(first.key)
  } else if (count === 3) {
    // all collapsed (default empty set)
  } else {
    // 2 sections: expand first one
    expandedSections.value.add(first.key)
  }
}

watch(
  availableSections,
  (newSections, oldSections) => {
    // Only auto-expand when going from "no content" to "has content"
    // oldSections is undefined on the first call with { immediate: true }
    if (
      !hasInitializedOnce.value &&
      newSections.length > 0 &&
      (!oldSections || oldSections.length === 0)
    ) {
      hasInitializedOnce.value = true
      initExpansion(newSections)
    }
    // After first init, never auto-overwrite user state
  },
  { immediate: true },
)

function isExpanded(key: SectionKey): boolean {
  return expandedSections.value.has(key)
}

const sectionRefs = ref<Record<SectionKey, HTMLElement | null>>({
  courses: null,
  questions: null,
  analysis: null,
})

async function toggle(key: SectionKey): Promise<void> {
  if (expandedSections.value.has(key)) {
    expandedSections.value.delete(key)
  } else {
    expandedSections.value.add(key)
    // Scroll to visible area after expansion
    await new Promise((r) => setTimeout(r, 0))
    sectionRefs.value[key]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }
  expandedSections.value = new Set(expandedSections.value)
}
</script>

<template>
  <div class="flex flex-col h-full bg-gray-50">
    <!-- Empty state -->
    <div
      v-if="availableSections.length === 0"
      class="flex flex-col items-center justify-center h-full text-gray-400"
    >
      <BookOpen class="w-12 h-12 mb-2 opacity-50" />
      <p class="text-sm">{{ t('widgets.courseCardsEmpty') }}</p>
    </div>

    <!-- Single section: render content directly without accordion header -->
    <div v-else-if="availableSections.length === 1" class="h-full overflow-y-auto">
      <QuizSection
        v-if="singleSection!.key === 'questions'"
        :title="title"
        :questions="questions"
        :quiz-type="quizType"
        :difficulty="quizDifficulty"
      />
      <CourseSection v-else-if="singleSection!.key === 'courses'" :courses="courses" />
      <DocumentAnalysisSection
        v-else-if="singleSection!.key === 'analysis'"
        :summary="summary"
        :key-points="keyPoints"
        :difficult-concepts="difficultConcepts"
        :suggested-topics="suggestedTopics"
        :doc-type="docType"
        :original-length="originalLength"
      />
    </div>

    <!-- Multiple sections: use accordion -->
    <div
      v-if="availableSections.length > 1"
      v-for="section in availableSections"
      :key="section.key"
      class="border-b border-gray-100"
    >
      <!-- Accordion header -->
      <button
        class="w-full flex items-center gap-3 px-4 py-3 bg-white hover:bg-gray-50 transition-colors text-left"
        @click="toggle(section.key)"
      >
        <!-- Color badge -->
        <span
          class="flex-shrink-0 w-7 h-7 rounded flex items-center justify-center"
          :style="{ backgroundColor: section.color + '20', color: section.color }"
        >
          <component :is="section.icon" class="w-4 h-4" />
        </span>
        <!-- Title -->
        <span class="flex-1 text-sm font-semibold text-gray-800">{{ t(section.labelKey) }}</span>
        <!-- Count badge -->
        <span
          class="text-xs px-2 py-0.5 rounded-full font-medium"
          :style="{ backgroundColor: section.color + '15', color: section.color }"
        >
          {{ section.count }}
        </span>
        <!-- Expand indicator -->
        <ChevronDown
          class="w-4 h-4 text-gray-400 transition-transform duration-200"
          :class="{ 'rotate-180': isExpanded(section.key) }"
        />
      </button>

      <!-- Accordion content -->
      <div
        v-show="isExpanded(section.key)"
        :ref="
          (el) => {
            sectionRefs[section.key] = el as HTMLElement
          }
        "
        class="overflow-y-auto"
        :class="section.key === 'questions' ? 'max-h-[60vh]' : 'max-h-[50vh]'"
      >
        <!-- Courses section -->
        <CourseSection v-if="section.key === 'courses'" :courses="courses" />

        <!-- Questions section -->
        <QuizSection
          v-else-if="section.key === 'questions'"
          :title="title"
          :questions="questions"
          :quiz-type="quizType"
          :difficulty="quizDifficulty"
        />

        <!-- Analysis section -->
        <DocumentAnalysisSection
          v-else-if="section.key === 'analysis'"
          :summary="summary"
          :key-points="keyPoints"
          :difficult-concepts="difficultConcepts"
          :suggested-topics="suggestedTopics"
          :doc-type="docType"
          :original-length="originalLength"
        />
      </div>
    </div>
  </div>
</template>
