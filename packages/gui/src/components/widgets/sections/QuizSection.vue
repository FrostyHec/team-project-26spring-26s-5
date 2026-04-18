<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { HelpCircle, CheckCircle2, XCircle, RotateCcw, Eye, EyeOff, Loader2 } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import {
  evaluateQuiz,
  type QuizQuestionForEval,
  type QuizEvaluationResult,
  type QuestionEvaluation,
} from '@/api/agent'
import type { QuizQuestion } from '../types'

const { t, locale } = useI18n()

const props = defineProps<{
  title: string
  questions: QuizQuestion[]
  quizType: string
}>()

// State
const userAnswers = ref<Record<number, string>>({})
const submitted = ref(false)
const showAnswers = ref(false)
const isEvaluating = ref(false)
const useAiGrading = ref(true)
const evaluationResults = ref<Record<string, QuestionEvaluation>>({})

// Reset state when questions change (e.g., new quiz arrives)
watch(
  () => props.questions,
  () => {
    userAnswers.value = {}
    submitted.value = false
    showAnswers.value = false
    evaluationResults.value = {}
  },
)

// Pre-compute evaluations once per question (avoids repeated getEvaluation calls in template)
const questionsWithEval = computed(() =>
  props.questions.map((q) => ({
    ...q,
    evaluation: evaluationResults.value[String(q.id)] || null,
  })),
)

const totalQuestions = computed(() => props.questions.length)

const answeredCount = computed(
  () => props.questions.filter((q) => userAnswers.value[q.id] !== undefined).length,
)

const allAnswered = computed(() => answeredCount.value >= totalQuestions.value)

const correctCount = computed(() => {
  if (!submitted.value) return 0
  return props.questions.filter((q) => {
    const eval_ = evaluationResults.value[String(q.id)]
    if (q.type === 'short_answer' && eval_) {
      return eval_.score >= (q.score ?? 10) * 0.5
    }
    if (q.type === 'fill_blank' && eval_) {
      return eval_.score >= (q.score ?? 5) * 0.5
    }
    return userAnswers.value[q.id] === q.correct_answer
  }).length
})

const totalScore = computed(() => {
  if (!submitted.value) return 0
  return props.questions.reduce((sum, q) => {
    const eval_ = evaluationResults.value[String(q.id)]
    if (q.type === 'short_answer' && eval_) return sum + eval_.score
    if (q.type === 'fill_blank' && eval_) return sum + eval_.score
    const questionScore =
      q.score ??
      (q.type === 'multiple_choice'
        ? 3
        : q.type === 'true_false'
          ? 1
          : q.type === 'fill_blank'
            ? 5
            : 10)
    return sum + (userAnswers.value[q.id] === q.correct_answer ? questionScore : 0)
  }, 0)
})

const maxScore = computed(() => {
  return props.questions.reduce((sum, q) => {
    const eval_ = evaluationResults.value[String(q.id)]
    if (eval_ && eval_.total_score_included === false) return sum
    return (
      sum +
      (q.score ??
        (q.type === 'multiple_choice'
          ? 3
          : q.type === 'true_false'
            ? 1
            : q.type === 'fill_blank'
              ? 5
              : 10))
    )
  }, 0)
})

const scorePercent = computed(() => {
  if (maxScore.value === 0) return 0
  return Math.round((totalScore.value / maxScore.value) * 100)
})

const scoreText = computed(() => {
  if (maxScore.value === 0) return '0/0'
  return `${totalScore.value}/${maxScore.value}`
})

const scoreLabel = computed(() => {
  return t('quiz.score', { text: scoreText.value })
})

function isCorrect(question: QuizQuestion): boolean | null {
  if (!submitted.value) return null
  if (question.type === 'short_answer') {
    const eval_ = evaluationResults.value[String(question.id)]
    if (eval_) return eval_.score >= (question.score ?? 10) * 0.5
    return null
  }
  if (question.type === 'fill_blank') {
    const eval_ = evaluationResults.value[String(question.id)]
    if (eval_) return eval_.score >= (question.score ?? 5) * 0.5
    return null
  }
  return userAnswers.value[question.id] === question.correct_answer
}

function getQuestionState(question: QuizQuestion): 'correct' | 'wrong' | 'unanswered' {
  if (!submitted.value) return 'unanswered'
  const correct = isCorrect(question)
  return correct === true ? 'correct' : correct === false ? 'wrong' : 'unanswered'
}

function selectAnswer(questionId: number, answer: string): void {
  if (submitted.value) return
  userAnswers.value[questionId] = answer
}

function getQuizTypeLabel(type: string): string {
  const typeMap: Record<string, string> = {
    multiple_choice: t('quiz.typeMultipleChoice'),
    true_false: t('quiz.typeTrueFalse'),
    fill_blank: t('quiz.typeFillBlank'),
    short_answer: t('quiz.typeShortAnswer'),
    mixed: t('quiz.typeMixed'),
  }
  return typeMap[type] || type
}

function getQuestionTypeLabel(type: string): string {
  const typeMap: Record<string, string> = {
    multiple_choice: t('quiz.typeMultipleChoice'),
    true_false: t('quiz.typeTrueFalse'),
    fill_blank: t('quiz.typeFillBlank'),
    short_answer: t('quiz.typeShortAnswer'),
  }
  return typeMap[type] || type
}

function getPlaceholder(type: string): string {
  if (type === 'fill_blank') {
    return t('quiz.placeholderFillBlank')
  }
  return t('quiz.placeholderShortAnswer')
}

/** Translate analysis key (from backend) to localized string. */
function getAnalysisText(analysis: string): string {
  const i18nKeyMap: Record<string, string> = {
    autoScored: 'quiz.autoScored',
    choiceNoManual: 'quiz.choiceNoManual',
    noAnswerProvided: 'quiz.noAnswerProvided',
    noAnalysisAvailable: 'quiz.noAnalysisAvailable',
    serviceUnavailableAuto: 'quiz.serviceUnavailableAuto',
    serviceUnavailableManual: 'quiz.serviceUnavailableManual',
  }
  // If analysis is an i18n key (from backend fallback), translate it;
  // otherwise it's raw LLM text — display as-is.
  const i18nKey = i18nKeyMap[analysis]
  return i18nKey ? t(i18nKey) : analysis
}

async function submitQuiz(): Promise<void> {
  if (isEvaluating.value) return
  isEvaluating.value = true
  let evaluationFailed = false
  try {
    const userAnswersForApi: Record<string, string> = {}
    for (const [k, v] of Object.entries(userAnswers.value)) {
      userAnswersForApi[k] = v
    }
    const questionsForApi: QuizQuestionForEval[] = props.questions.map((q) => ({
      id: q.id,
      type: q.type,
      question: q.question,
      options: q.options,
      correct_answer: q.correct_answer,
      explanation: q.explanation,
      score:
        q.score ??
        (q.type === 'multiple_choice'
          ? 3
          : q.type === 'true_false'
            ? 1
            : q.type === 'fill_blank'
              ? 5
              : 10),
    }))
    const result: QuizEvaluationResult = await evaluateQuiz(
      questionsForApi,
      userAnswersForApi,
      useAiGrading.value,
      locale.value,
    )
    evaluationResults.value = result.evaluations
  } catch (err) {
    console.error('Evaluation failed:', err)
    evaluationFailed = true
  } finally {
    isEvaluating.value = false
    submitted.value = true
    showAnswers.value = true
  }
  if (evaluationFailed) {
    for (const q of props.questions) {
      if (
        (q.type === 'short_answer' || q.type === 'fill_blank') &&
        !evaluationResults.value[String(q.id)]
      ) {
        evaluationResults.value[String(q.id)] = {
          score: 0,
          standard_answer: q.correct_answer,
          analysis: t('quiz.serviceUnavailableManual'),
          total_score_included: q.type === 'short_answer' ? false : true,
        }
      }
    }
  }
}

function resetQuiz(): void {
  userAnswers.value = {}
  submitted.value = false
  showAnswers.value = false
  evaluationResults.value = {}
}

function toggleShowAnswers(): void {
  showAnswers.value = !showAnswers.value
}

function defaultScore(q: QuizQuestion): number {
  return (
    q.score ??
    (q.type === 'multiple_choice'
      ? 3
      : q.type === 'true_false'
        ? 1
        : q.type === 'fill_blank'
          ? 5
          : 10)
  )
}
</script>

<template>
  <div class="flex flex-col h-full bg-gray-50">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200 px-4 py-3 flex-shrink-0">
      <div class="flex items-center justify-between mb-2">
        <div class="flex items-center gap-2">
          <HelpCircle class="w-5 h-5 text-purple-600" />
          <h3 class="font-semibold text-gray-800">{{ title }}</h3>
        </div>
        <button
          v-if="submitted"
          class="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded border border-gray-200 hover:bg-gray-50 transition-colors"
          @click="toggleShowAnswers"
        >
          <component :is="showAnswers ? EyeOff : Eye" class="w-3.5 h-3.5" />
          {{ showAnswers ? t('quiz.hideAnswers') : t('quiz.showAnswers') }}
        </button>
      </div>
      <!-- Progress bar -->
      <div class="flex items-center gap-3">
        <div class="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            class="h-full bg-purple-500 transition-all duration-300"
            :style="{
              width: `${totalQuestions > 0 ? (answeredCount / totalQuestions) * 100 : 0}%`,
            }"
          />
        </div>
        <span class="text-xs text-gray-500 font-medium shrink-0">
          {{ answeredCount }}/{{ totalQuestions }}
        </span>
      </div>
      <!-- Score -->
      <div v-if="submitted" class="mt-3 flex items-center gap-3">
        <div
          class="flex-1 p-3 rounded-lg text-center"
          :class="
            scorePercent >= 80
              ? 'bg-green-50 border border-green-200'
              : scorePercent >= 60
                ? 'bg-yellow-50 border border-yellow-200'
                : 'bg-red-50 border border-red-200'
          "
        >
          <div
            class="text-2xl font-bold"
            :class="
              scorePercent >= 80
                ? 'text-green-600'
                : scorePercent >= 60
                  ? 'text-yellow-600'
                  : 'text-red-600'
            "
          >
            {{ scorePercent }}%
          </div>
          <div class="text-xs text-gray-500">{{ scoreLabel }}</div>
        </div>
        <button
          class="flex items-center gap-1.5 px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition-colors"
          @click="resetQuiz"
        >
          <RotateCcw class="w-4 h-4" />
          {{ t('quiz.resetQuiz') }}
        </button>
      </div>
      <!-- Quiz type badge -->
      <div class="mt-2 flex gap-2">
        <span
          class="px-2 py-0.5 text-xs rounded-full"
          :class="{
            'bg-blue-50 text-blue-600': quizType === 'multiple_choice',
            'bg-green-50 text-green-600': quizType === 'true_false',
            'bg-orange-50 text-orange-600': quizType === 'fill_blank',
            'bg-purple-50 text-purple-600': quizType === 'short_answer',
            'bg-gray-50 text-gray-600': quizType === 'mixed',
          }"
        >
          {{ getQuizTypeLabel(quizType) }}
        </span>
      </div>
    </div>

    <!-- Questions list -->
    <div class="flex-1 overflow-y-auto p-4 space-y-4">
      <div
        v-if="questions.length === 0"
        class="flex flex-col items-center justify-center py-12 text-gray-400"
      >
        <HelpCircle class="w-12 h-12 mb-2" />
        <p class="text-sm">{{ t('quiz.noQuestions') }}</p>
      </div>

      <template v-else>
        <div
          v-for="(question, index) in questionsWithEval"
          :key="question.id"
          class="bg-white rounded-xl border transition-all duration-200"
          :class="{
            'border-green-300 bg-green-50': getQuestionState(question) === 'correct',
            'border-red-300 bg-red-50': getQuestionState(question) === 'wrong',
            'border-gray-200': getQuestionState(question) === 'unanswered',
          }"
        >
          <!-- Question header -->
          <div class="p-4 border-b border-gray-100">
            <div class="flex items-start gap-3">
              <span
                class="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full text-xs font-medium"
                :class="{
                  'bg-green-100 text-green-700': getQuestionState(question) === 'correct',
                  'bg-red-100 text-red-700': getQuestionState(question) === 'wrong',
                  'bg-purple-100 text-purple-700': getQuestionState(question) === 'unanswered',
                }"
              >
                {{ index + 1 }}
              </span>
              <div class="flex-1 min-w-0">
                <p class="text-sm text-gray-800 font-medium leading-relaxed whitespace-pre-wrap">
                  {{ question.question }}
                </p>
                <span
                  class="inline-block mt-1.5 px-2 py-0.5 text-xs rounded-full"
                  :class="{
                    'bg-blue-50 text-blue-600': question.type === 'multiple_choice',
                    'bg-green-50 text-green-600': question.type === 'true_false',
                    'bg-orange-50 text-orange-600': question.type === 'fill_blank',
                    'bg-purple-50 text-purple-600': question.type === 'short_answer',
                  }"
                >
                  {{ getQuestionTypeLabel(question.type) }}
                  {{ t('quiz.score', { text: defaultScore(question) }) }}
                </span>
                <!-- fill_blank and short_answer score badge — uses pre-cached evaluation -->
                <span
                  v-if="
                    submitted &&
                    (question.type === 'fill_blank' || question.type === 'short_answer') &&
                    question.evaluation
                  "
                  class="inline-block ml-1.5 px-2 py-0.5 text-xs rounded-full"
                  :class="
                    question.evaluation!.score /
                      (question.score ?? (question.type === 'fill_blank' ? 5 : 10)) >=
                    0.7
                      ? 'bg-green-100 text-green-700'
                      : question.evaluation!.score /
                            (question.score ?? (question.type === 'fill_blank' ? 5 : 10)) >=
                          0.5
                        ? 'bg-yellow-100 text-yellow-700'
                        : 'bg-red-100 text-red-700'
                  "
                >
                  {{ question.evaluation!.score }}/{{
                    question.score ?? (question.type === 'fill_blank' ? 5 : 10)
                  }}
                </span>
              </div>
              <!-- Result icon -->
              <div v-if="submitted" class="flex-shrink-0">
                <CheckCircle2 v-if="isCorrect(question) === true" class="w-5 h-5 text-green-600" />
                <XCircle v-else-if="isCorrect(question) === false" class="w-5 h-5 text-red-600" />
              </div>
            </div>
          </div>

          <!-- Options (for multiple_choice and true_false) -->
          <div
            v-if="question.type === 'multiple_choice' || question.type === 'true_false'"
            class="p-4 space-y-2"
          >
            <button
              v-for="(option, optIndex) in question.options"
              :key="optIndex"
              class="w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all duration-150"
              :class="{
                'border-green-300 bg-green-100': showAnswers && option === question.correct_answer,
                'border-red-300 bg-red-100':
                  showAnswers &&
                  userAnswers[question.id] === option &&
                  option !== question.correct_answer,
                'border-blue-300 bg-blue-50': !showAnswers && userAnswers[question.id] === option,
                'border-gray-200 hover:border-purple-300 hover:bg-purple-50':
                  !showAnswers && userAnswers[question.id] !== option,
                'border-gray-200 cursor-default': submitted && userAnswers[question.id] !== option,
              }"
              :disabled="submitted"
              @click="selectAnswer(question.id, option)"
            >
              <span
                class="flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors"
                :class="{
                  'border-green-500 bg-green-500':
                    showAnswers && option === question.correct_answer,
                  'border-red-500 bg-red-500':
                    showAnswers &&
                    userAnswers[question.id] === option &&
                    option !== question.correct_answer,
                  'border-blue-500 bg-blue-500':
                    !showAnswers && userAnswers[question.id] === option,
                  'border-gray-300': !showAnswers && userAnswers[question.id] !== option,
                  'border-gray-300 bg-gray-100': submitted && userAnswers[question.id] !== option,
                }"
              >
                <span
                  v-if="!showAnswers && userAnswers[question.id] === option"
                  class="w-2 h-2 rounded-full bg-white"
                />
                <CheckCircle2
                  v-if="showAnswers && option === question.correct_answer"
                  class="w-3 h-3 text-white"
                />
              </span>
              <span
                class="text-sm"
                :class="{
                  'text-green-700 font-medium': showAnswers && option === question.correct_answer,
                  'text-red-700':
                    showAnswers &&
                    userAnswers[question.id] === option &&
                    option !== question.correct_answer,
                  'text-gray-700':
                    !showAnswers ||
                    (userAnswers[question.id] !== option && option !== question.correct_answer),
                }"
              >
                {{ option }}
              </span>
            </button>
          </div>

          <!-- Fill blank and short answer input -->
          <div
            v-if="question.type === 'fill_blank' || question.type === 'short_answer'"
            class="p-4"
          >
            <div v-if="!submitted" class="mb-3">
              <textarea
                v-model="userAnswers[question.id]"
                class="w-full p-3 border border-gray-200 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-purple-300 focus:border-purple-300 transition-colors"
                rows="3"
                :placeholder="getPlaceholder(question.type)"
              />
            </div>
            <div v-if="submitted">
              <div class="mb-3 p-3 bg-gray-50 border border-gray-200 rounded-lg">
                <div class="text-xs text-gray-500 mb-1">{{ t('quiz.yourAnswer') }}</div>
                <div class="text-sm text-gray-700 whitespace-pre-wrap">
                  {{ userAnswers[question.id] || t('quiz.notAnswered') }}
                </div>
              </div>
              <div v-if="isEvaluating" class="flex items-center justify-center py-4 text-gray-400">
                <Loader2 class="w-5 h-5 animate-spin mr-2" />
                <span class="text-sm">{{ t('quiz.aiGrading') }}</span>
              </div>
              <template v-else-if="question.evaluation">
                <!-- Standard answer -->
                <div class="mb-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                  <div class="text-xs text-green-600 font-medium mb-1">
                    {{ t('quiz.referenceAnswer') }}
                  </div>
                  <div class="text-sm text-green-700">
                    {{ question.evaluation!.standard_answer }}
                  </div>
                </div>
                <!-- Score -->
                <div
                  v-if="question.evaluation!.total_score_included !== false"
                  class="mb-2 text-center"
                >
                  <span
                    class="text-2xl font-bold"
                    :class="
                      question.evaluation!.score >= 7
                        ? 'text-green-600'
                        : question.evaluation!.score >= 5
                          ? 'text-yellow-600'
                          : 'text-red-600'
                    "
                  >
                    {{ question.evaluation!.score }}
                  </span>
                  <span class="text-gray-400 text-lg"
                    >/{{ question.score ?? (question.type === 'fill_blank' ? 5 : 10) }}</span
                  >
                </div>
                <div
                  v-if="question.evaluation!.total_score_included === false"
                  class="text-center text-gray-400 text-sm mb-2"
                >
                  {{ t('quiz.aiGradingDisabled') }}
                </div>
                <!-- Analysis -->
                <div
                  v-if="question.evaluation!.analysis"
                  class="p-3 bg-purple-50 border border-purple-100 rounded-lg"
                >
                  <div class="text-xs text-purple-600 font-medium mb-1">
                    {{ t('quiz.analysisLabel') }}
                  </div>
                  <div class="text-sm text-gray-700 whitespace-pre-wrap">
                    {{ getAnalysisText(question.evaluation!.analysis) }}
                  </div>
                </div>
              </template>
              <div
                v-else
                class="p-3 bg-gray-50 border border-gray-200 rounded-lg text-center text-sm text-gray-500"
              >
                {{ t('quiz.serviceUnavailableManual') }}
              </div>
            </div>
          </div>

          <!-- Explanation (for non fill_blank/short_answer, shown after submit) -->
          <div
            v-if="
              submitted &&
              question.type !== 'fill_blank' &&
              question.type !== 'short_answer' &&
              question.explanation
            "
            class="px-4 pb-4"
          >
            <div class="p-3 bg-purple-50 border border-purple-100 rounded-lg">
              <div class="text-xs text-purple-600 font-medium mb-1">
                {{ t('quiz.explanation') }}
              </div>
              <p class="text-sm text-gray-700">{{ question.explanation }}</p>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- Footer: Submit button -->
    <div
      v-if="!submitted && questions.length > 0"
      class="bg-white border-t border-gray-200 px-4 py-3 flex-shrink-0"
    >
      <div class="mb-3 flex items-center gap-2">
        <input
          id="ai-grading-toggle"
          v-model="useAiGrading"
          type="checkbox"
          class="w-4 h-4 text-purple-600 rounded border-gray-300"
        />
        <label for="ai-grading-toggle" class="text-sm text-gray-600">
          {{ t('quiz.enableAiGrading') }}
        </label>
      </div>
      <button
        class="w-full py-2.5 rounded-lg font-medium text-white transition-colors flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-700"
        :disabled="isEvaluating"
        @click="submitQuiz"
      >
        <Loader2 v-if="isEvaluating" class="w-4 h-4 animate-spin" />
        {{ isEvaluating ? t('quiz.aiGrading') : t('quiz.submitAnswers') }}
      </button>
    </div>
  </div>
</template>
