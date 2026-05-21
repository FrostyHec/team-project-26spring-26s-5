<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  BookOpen,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Delete,
  Eye,
  EyeOff,
  Filter,
  HelpCircle,
  Loader2,
  RotateCcw,
  XCircle,
} from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import {
  deleteWrongQuestion,
  getWrongQuestions,
  wrongQuestionToQuizQuestion,
  type WrongQuestion,
} from '@/api/wrongQuestions'
import {
  evaluateQuiz,
  type QuizQuestionForEval,
  type QuizEvaluationResult,
  type QuestionEvaluation,
} from '@/api/agent'
import type { QuizQuestion } from '../types'

const { t, locale } = useI18n()

type PracticeMode = 'single' | 'batch'

const wrongQuestions = ref<WrongQuestion[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

// Practice mode
const practiceMode = ref<PracticeMode>('batch')
const groupByType = ref(false)

// Current single question index
const currentQuestionIndex = ref(0)
const userAnswer = ref('')
const submitted = ref(false)
const showAnswer = ref(false)
const isEvaluating = ref(false)
const useAiGrading = ref(true)
const evaluationResult = ref<QuestionEvaluation | null>(null)

// Batch mode answers
const batchAnswers = ref<Record<number, string>>({})
const batchSubmitted = ref(false)
const batchShowAnswers = ref(false)
const batchIsEvaluating = ref(false)
const batchEvaluationResults = ref<Record<string, QuestionEvaluation>>({})

// Load questions
async function loadQuestions() {
  loading.value = true
  error.value = null
  try {
    const response = await getWrongQuestions()
    wrongQuestions.value = response.questions
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load questions'
  } finally {
    loading.value = false
  }
}

loadQuestions()

// Group questions by type
const groupedQuestions = computed(() => {
  if (!groupByType.value) return null
  const groups: Record<string, WrongQuestion[]> = {}
  for (const q of wrongQuestions.value) {
    const type = q.question_type
    if (!groups[type]) {
      groups[type] = []
    }
    groups[type]!.push(q)
  }
  return groups
})

// Current single question
const currentQuestion = computed(() => {
  if (wrongQuestions.value.length === 0) return null
  const idx = currentQuestionIndex.value
  return wrongQuestions.value[idx] ?? null
})

// Score for single mode
const singleScore = computed(() => {
  if (!submitted.value || !evaluationResult.value) return null
  const q = currentQuestion.value
  if (!q) return null
  const maxScore = getDefaultScore(q.question_type)
  return {
    score: evaluationResult.value.score,
    maxScore,
    percent: Math.round((evaluationResult.value.score / maxScore) * 100),
  }
})

// Score for batch mode
const batchScorePercent = computed(() => {
  if (!batchSubmitted.value) return 0
  let total = 0
  let maxTotal = 0
  for (const q of wrongQuestions.value) {
    const eval_ = batchEvaluationResults.value[String(q.id)]
    if (eval_ && eval_.total_score_included === false) continue
    const maxScore = getDefaultScore(q.question_type)
    maxTotal += maxScore
    if (q.question_type === 'fill_blank' || q.question_type === 'short_answer') {
      total += eval_?.score ?? 0
    } else {
      if (batchAnswers.value[q.id] === q.correct_answer) {
        total += maxScore
      }
    }
  }
  if (maxTotal === 0) return 0
  return Math.round((total / maxTotal) * 100)
})

function getDefaultScore(type: string): number {
  switch (type) {
    case 'multiple_choice':
      return 3
    case 'true_false':
      return 1
    case 'fill_blank':
      return 5
    case 'short_answer':
      return 10
    default:
      return 5
  }
}

function getTypeLabel(type: string): string {
  const map: Record<string, string> = {
    multiple_choice: t('quiz.typeMultipleChoice'),
    true_false: t('quiz.typeTrueFalse'),
    fill_blank: t('quiz.typeFillBlank'),
    short_answer: t('quiz.typeShortAnswer'),
  }
  return map[type] || type
}

function getPlaceholder(type: string): string {
  if (type === 'fill_blank') {
    return t('quiz.placeholderFillBlank')
  }
  return t('quiz.placeholderShortAnswer')
}

// Single mode: submit
async function submitSingleAnswer() {
  const q = currentQuestion.value
  if (!q || isEvaluating.value) return
  isEvaluating.value = true
  submitted.value = true
  showAnswer.value = true

  const maxScore = getDefaultScore(q.question_type)

  // Pre-set empty answer evaluation
  if (!userAnswer.value.trim()) {
    evaluationResult.value = {
      score: 0,
      standard_answer: q.correct_answer,
      analysis: 'noAnswerProvided',
      total_score_included: true,
    }
    isEvaluating.value = false
    return
  }

  // Call evaluation API for fill_blank and short_answer
  if (q.question_type === 'fill_blank' || q.question_type === 'short_answer') {
    const questionsForApi: QuizQuestionForEval[] = [
      {
        id: q.id,
        type: q.question_type,
        question: q.question,
        options: q.options,
        correct_answer: q.correct_answer,
        explanation: q.explanation,
        score: maxScore,
      },
    ]
    const userAnswersForApi: Record<string, string> = { [String(q.id)]: userAnswer.value }

    try {
      const result: QuizEvaluationResult = await evaluateQuiz(
        questionsForApi,
        userAnswersForApi,
        useAiGrading.value,
        locale.value,
      )
      evaluationResult.value = result.evaluations[String(q.id)] ?? null
    } catch {
      // Fallback to exact match for fill_blank
      if (q.question_type === 'fill_blank') {
        const correct = userAnswer.value.trim() === q.correct_answer.trim()
        evaluationResult.value = {
          score: correct ? maxScore : 0,
          standard_answer: q.correct_answer,
          analysis: 'serviceUnavailableAuto',
          total_score_included: true,
        }
      } else {
        evaluationResult.value = {
          score: 0,
          standard_answer: q.correct_answer,
          analysis: 'serviceUnavailableManual',
          total_score_included: false,
        }
      }
    }
  } else {
    // Auto-score for multiple_choice and true_false
    const correct = userAnswer.value === q.correct_answer
    evaluationResult.value = {
      score: correct ? maxScore : 0,
      standard_answer: q.correct_answer,
      analysis: 'autoScored',
      total_score_included: true,
    }
  }

  isEvaluating.value = false
}

// Single mode: next question
function nextQuestion() {
  if (currentQuestionIndex.value < wrongQuestions.value.length - 1) {
    currentQuestionIndex.value++
    resetSingleQuestion()
  }
}

function prevQuestion() {
  if (currentQuestionIndex.value > 0) {
    currentQuestionIndex.value--
    resetSingleQuestion()
  }
}

function resetSingleQuestion() {
  userAnswer.value = ''
  submitted.value = false
  showAnswer.value = false
  evaluationResult.value = null
}

function selectOption(answer: string) {
  if (submitted.value) return
  userAnswer.value = answer
}

function isCorrectAnswer(option: string): boolean {
  const q = currentQuestion.value
  if (!q) return false
  return option === q.correct_answer
}

function isWrongAnswer(option: string): boolean {
  const q = currentQuestion.value
  if (!q || !submitted.value) return false
  return option === userAnswer.value && option !== q.correct_answer
}

// Batch mode: submit all
async function submitBatch() {
  if (batchIsEvaluating.value) return
  batchIsEvaluating.value = true
  batchSubmitted.value = true
  batchShowAnswers.value = true

  // Pre-set empty answers
  for (const q of wrongQuestions.value) {
    if (
      (q.question_type === 'fill_blank' || q.question_type === 'short_answer') &&
      batchAnswers.value[q.id] === undefined
    ) {
      batchEvaluationResults.value[String(q.id)] = {
        score: 0,
        standard_answer: q.correct_answer,
        analysis: 'noAnswerProvided',
        total_score_included: true,
      }
    }
  }

  const answeredQuestions = wrongQuestions.value.filter(
    (q) => batchAnswers.value[q.id] !== undefined,
  )

  if (answeredQuestions.length > 0) {
    const questionsForApi: QuizQuestionForEval[] = answeredQuestions.map((q) => ({
      id: q.id,
      type: q.question_type,
      question: q.question,
      options: q.options,
      correct_answer: q.correct_answer,
      explanation: q.explanation,
      score: getDefaultScore(q.question_type),
    }))
    const userAnswersForApi: Record<string, string> = {}
    for (const q of answeredQuestions) {
      const answer = batchAnswers.value[q.id]
      if (answer !== undefined) {
        userAnswersForApi[String(q.id)] = answer
      }
    }

    try {
      const result: QuizEvaluationResult = await evaluateQuiz(
        questionsForApi,
        userAnswersForApi,
        useAiGrading.value,
        locale.value,
      )
      Object.assign(batchEvaluationResults.value, result.evaluations)
    } catch {
      for (const q of answeredQuestions) {
        const existing = batchEvaluationResults.value[String(q.id)]
        if (
          q.question_type === 'short_answer' &&
          (existing === undefined || existing.total_score_included !== false)
        ) {
          batchEvaluationResults.value[String(q.id)] = {
            score: 0,
            standard_answer: q.correct_answer,
            analysis: 'serviceUnavailableManual',
            total_score_included: false,
          }
        }
      }
    }
  }

  batchIsEvaluating.value = false
}

function resetBatch() {
  batchAnswers.value = {}
  batchSubmitted.value = false
  batchShowAnswers.value = false
  batchEvaluationResults.value = {}
}

// Delete question
async function handleDelete(id: number) {
  try {
    await deleteWrongQuestion(id)
    wrongQuestions.value = wrongQuestions.value.filter((q) => q.id !== id)
    // Adjust current index if needed
    if (practiceMode.value === 'single') {
      if (currentQuestionIndex.value >= wrongQuestions.value.length) {
        currentQuestionIndex.value = Math.max(0, wrongQuestions.value.length - 1)
      }
      resetSingleQuestion()
    }
  } catch {
    error.value = 'Failed to delete question'
  }
}

// Toggle group by type
watch(groupByType, () => {
  if (practiceMode.value === 'single') {
    resetSingleQuestion()
  }
})

// Reset when switching modes
watch(practiceMode, () => {
  currentQuestionIndex.value = 0
  resetSingleQuestion()
  resetBatch()
})

// Analysis text
function getAnalysisText(analysis: string): string {
  const i18nKeyMap: Record<string, string> = {
    autoScored: 'quiz.autoScored',
    choiceNoManual: 'quiz.choiceNoManual',
    noAnswerProvided: 'quiz.noAnswerProvided',
    noAnalysisAvailable: 'quiz.noAnalysisAvailable',
    serviceUnavailableAuto: 'quiz.serviceUnavailableAuto',
    serviceUnavailableManual: 'quiz.serviceUnavailableManual',
  }
  const i18nKey = i18nKeyMap[analysis]
  return i18nKey ? t(i18nKey) : analysis
}

// Delete confirmation modal state
const showDeleteConfirm = ref(false)
const questionToDelete = ref<number | null>(null)

function confirmDelete(id: number) {
  questionToDelete.value = id
  showDeleteConfirm.value = true
}

function cancelDelete() {
  questionToDelete.value = null
  showDeleteConfirm.value = false
}

async function executeDelete() {
  if (questionToDelete.value === null) return
  const id = questionToDelete.value
  questionToDelete.value = null
  showDeleteConfirm.value = false
  await handleDelete(id)
}
</script>

<template>
  <div class="flex flex-col h-full bg-gray-50">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200 px-4 py-3 flex-shrink-0">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2">
          <BookOpen class="w-5 h-5 text-purple-600" />
          <h3 class="font-semibold text-gray-800">{{ t('widgets.wrongQuestionBook') }}</h3>
        </div>
        <span class="text-xs text-gray-500">
          {{ wrongQuestions.length }} {{ t('quiz.questions') }}
        </span>
      </div>

      <!-- Mode toggle -->
      <div class="flex items-center gap-2 mb-3">
        <button
          class="px-3 py-1.5 text-sm rounded-lg border transition-colors"
          :class="
            practiceMode === 'batch'
              ? 'bg-purple-100 border-purple-300 text-purple-700'
              : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
          "
          @click="practiceMode = 'batch'"
        >
          {{ t('wrongQuestionBook.batchMode') }}
        </button>
        <button
          class="px-3 py-1.5 text-sm rounded-lg border transition-colors"
          :class="
            practiceMode === 'single'
              ? 'bg-purple-100 border-purple-300 text-purple-700'
              : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
          "
          @click="practiceMode = 'single'"
        >
          {{ t('wrongQuestionBook.singleMode') }}
        </button>
        <button
          class="ml-auto flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border transition-colors"
          :class="
            groupByType
              ? 'bg-blue-100 border-blue-300 text-blue-700'
              : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
          "
          @click="groupByType = !groupByType"
        >
          <Filter class="w-3.5 h-3.5" />
          {{ t('wrongQuestionBook.groupByType') }}
        </button>
      </div>

      <!-- AI grading toggle (only for fill_blank and short_answer) -->
      <div class="flex items-center gap-2">
        <input
          id="ai-grading-toggle-wqb"
          v-model="useAiGrading"
          type="checkbox"
          class="w-4 h-4 text-purple-600 rounded border-gray-300"
        />
        <label for="ai-grading-toggle-wqb" class="text-sm text-gray-600">
          {{ t('quiz.enableAiGrading') }}
        </label>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-4">
      <!-- Loading -->
      <div v-if="loading" class="flex flex-col items-center justify-center py-12 text-gray-400">
        <Loader2 class="w-8 h-8 animate-spin mb-2" />
        <p class="text-sm">{{ t('common.loading') }}</p>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="flex flex-col items-center justify-center py-12 text-red-400">
        <XCircle class="w-8 h-8 mb-2" />
        <p class="text-sm">{{ error }}</p>
        <button
          class="mt-2 px-3 py-1.5 text-sm text-purple-600 hover:text-purple-700"
          @click="loadQuestions"
        >
          {{ t('common.retry') }}
        </button>
      </div>

      <!-- Empty -->
      <div
        v-else-if="wrongQuestions.length === 0"
        class="flex flex-col items-center justify-center py-12 text-gray-400"
      >
        <BookOpen class="w-12 h-12 mb-2" />
        <p class="text-sm">{{ t('wrongQuestionBook.empty') }}</p>
      </div>

      <!-- Single Mode -->
      <template v-else-if="practiceMode === 'single'">
        <!-- Question indicator -->
        <div class="flex items-center justify-between mb-4">
          <button
            class="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
            @click="prevQuestion"
          >
            <ChevronLeft class="w-4 h-4" />
            {{ t('wrongQuestionBook.previous') }}
          </button>
          <span class="text-sm text-gray-600">
            {{ currentQuestionIndex + 1 }} / {{ wrongQuestions.length }}
          </span>
          <button
            class="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
            @click="nextQuestion"
          >
            {{ t('wrongQuestionBook.next') }}
            <ChevronRight class="w-4 h-4" />
          </button>
        </div>

        <div v-if="currentQuestion" class="space-y-4">
          <!-- Score display -->
          <div
            v-if="submitted && singleScore"
            class="p-4 rounded-lg text-center"
            :class="
              singleScore.percent >= 80
                ? 'bg-green-50 border border-green-200'
                : singleScore.percent >= 60
                  ? 'bg-yellow-50 border border-yellow-200'
                  : 'bg-red-50 border border-red-200'
            "
          >
            <div
              class="text-2xl font-bold"
              :class="
                singleScore.percent >= 80
                  ? 'text-green-600'
                  : singleScore.percent >= 60
                    ? 'text-yellow-600'
                    : 'text-red-600'
              "
            >
              {{ singleScore.percent }}%
            </div>
            <div class="text-xs text-gray-500">
              {{ singleScore.score }} / {{ singleScore.maxScore }}
            </div>
          </div>

          <!-- Question card -->
          <div class="bg-white rounded-xl border border-gray-200">
            <div class="p-4 border-b border-gray-100">
              <div class="flex items-start gap-3">
                <span
                  class="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full bg-purple-100 text-purple-700 text-xs font-medium"
                >
                  {{ currentQuestionIndex + 1 }}
                </span>
                <div class="flex-1 min-w-0">
                  <p class="text-sm text-gray-800 font-medium leading-relaxed whitespace-pre-wrap">
                    {{ currentQuestion.question }}
                  </p>
                  <span
                    class="inline-block mt-1.5 px-2 py-0.5 text-xs rounded-full"
                    :class="{
                      'bg-blue-50 text-blue-600':
                        currentQuestion.question_type === 'multiple_choice',
                      'bg-green-50 text-green-600': currentQuestion.question_type === 'true_false',
                      'bg-orange-50 text-orange-600':
                        currentQuestion.question_type === 'fill_blank',
                      'bg-purple-50 text-purple-600':
                        currentQuestion.question_type === 'short_answer',
                    }"
                  >
                    {{ getTypeLabel(currentQuestion.question_type) }}
                    {{ t('quiz.score', { text: getDefaultScore(currentQuestion.question_type) }) }}
                  </span>
                </div>
                <button
                  class="flex-shrink-0 p-1.5 text-gray-400 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors"
                  :title="t('wrongQuestionBook.deleteQuestion')"
                  @click="confirmDelete(currentQuestion.id)"
                >
                  <Delete class="w-4 h-4" />
                </button>
              </div>
            </div>

            <!-- Options (multiple_choice / true_false) -->
            <div
              v-if="
                currentQuestion.question_type === 'multiple_choice' ||
                currentQuestion.question_type === 'true_false'
              "
              class="p-4 space-y-2"
            >
              <button
                v-for="(option, optIndex) in currentQuestion.options"
                :key="optIndex"
                class="w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all duration-150"
                :class="{
                  'border-green-300 bg-green-100': showAnswer && isCorrectAnswer(option),
                  'border-red-300 bg-red-100': showAnswer && isWrongAnswer(option),
                  'border-blue-300 bg-blue-50': !showAnswer && userAnswer === option,
                  'border-gray-200 hover:border-purple-300 hover:bg-purple-50':
                    !showAnswer && userAnswer !== option,
                  'border-gray-200 cursor-default': submitted && userAnswer !== option,
                }"
                :disabled="submitted"
                @click="selectOption(option)"
              >
                <span
                  class="flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors"
                  :class="{
                    'border-green-500 bg-green-500': showAnswer && isCorrectAnswer(option),
                    'border-red-500 bg-red-500': showAnswer && isWrongAnswer(option),
                    'border-blue-500 bg-blue-500': !showAnswer && userAnswer === option,
                    'border-gray-300': !showAnswer && userAnswer !== option,
                    'border-gray-300 bg-gray-100': submitted && userAnswer !== option,
                  }"
                >
                  <span
                    v-if="!showAnswer && userAnswer === option"
                    class="w-2 h-2 rounded-full bg-white"
                  />
                  <CheckCircle2
                    v-if="showAnswer && (isCorrectAnswer(option) || isWrongAnswer(option))"
                    class="w-3 h-3 text-white"
                  />
                </span>
                <span
                  class="text-sm"
                  :class="{
                    'text-green-700 font-medium': showAnswer && isCorrectAnswer(option),
                    'text-red-700': showAnswer && isWrongAnswer(option),
                    'text-gray-700':
                      !showAnswer || (!isCorrectAnswer(option) && !isWrongAnswer(option)),
                  }"
                >
                  {{ option }}
                </span>
              </button>
            </div>

            <!-- Fill blank / Short answer input -->
            <div
              v-if="
                currentQuestion.question_type === 'fill_blank' ||
                currentQuestion.question_type === 'short_answer'
              "
              class="p-4"
            >
              <div v-if="!submitted">
                <textarea
                  v-model="userAnswer"
                  class="w-full p-3 border border-gray-200 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-purple-300 focus:border-purple-300 transition-colors"
                  rows="3"
                  :placeholder="getPlaceholder(currentQuestion.question_type)"
                />
              </div>
              <div v-else class="space-y-3">
                <div class="mb-3 p-3 bg-gray-50 border border-gray-200 rounded-lg">
                  <div class="text-xs text-gray-500 mb-1">{{ t('quiz.yourAnswer') }}</div>
                  <div class="text-sm text-gray-700 whitespace-pre-wrap">
                    {{ userAnswer || t('quiz.notAnswered') }}
                  </div>
                </div>
                <div
                  v-if="isEvaluating"
                  class="flex items-center justify-center py-4 text-gray-400"
                >
                  <Loader2 class="w-5 h-5 animate-spin mr-2" />
                  <span class="text-sm">{{ t('quiz.aiGrading') }}</span>
                </div>
                <template v-else-if="evaluationResult">
                  <div class="mb-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                    <div class="text-xs text-green-600 font-medium mb-1">
                      {{ t('quiz.referenceAnswer') }}
                    </div>
                    <div class="text-sm text-green-700">
                      {{ evaluationResult.standard_answer }}
                    </div>
                  </div>
                  <div
                    v-if="evaluationResult.total_score_included !== false"
                    class="mb-2 text-center"
                  >
                    <span
                      class="text-2xl font-bold"
                      :class="
                        evaluationResult.score >= 7
                          ? 'text-green-600'
                          : evaluationResult.score >= 5
                            ? 'text-yellow-600'
                            : 'text-red-600'
                      "
                    >
                      {{ evaluationResult.score }}
                    </span>
                    <span class="text-gray-400 text-lg">
                      / {{ getDefaultScore(currentQuestion.question_type) }}
                    </span>
                  </div>
                  <div
                    v-if="evaluationResult.analysis"
                    class="p-3 bg-purple-50 border border-purple-100 rounded-lg"
                  >
                    <div class="text-xs text-purple-600 font-medium mb-1">
                      {{ t('quiz.analysisLabel') }}
                    </div>
                    <div class="text-sm text-gray-700 whitespace-pre-wrap">
                      {{ getAnalysisText(evaluationResult.analysis) }}
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </div>

          <!-- Submit / Next button -->
          <div class="flex gap-2">
            <button
              v-if="!submitted"
              class="flex-1 py-2.5 rounded-lg font-medium text-white transition-colors flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50"
              :disabled="
                !userAnswer &&
                (currentQuestion.question_type === 'fill_blank' ||
                  currentQuestion.question_type === 'short_answer')
              "
              @click="submitSingleAnswer"
            >
              <Loader2 v-if="isEvaluating" class="w-4 h-4 animate-spin" />
              {{ t('quiz.submitAnswers') }}
            </button>
            <button
              v-else
              class="flex-1 py-2.5 rounded-lg font-medium text-white transition-colors flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-700"
              @click="nextQuestion"
            >
              {{
                currentQuestionIndex < wrongQuestions.length - 1
                  ? t('wrongQuestionBook.next')
                  : t('wrongQuestionBook.finish')
              }}
            </button>
            <button
              class="px-4 py-2.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
              @click="resetSingleQuestion"
            >
              <RotateCcw class="w-4 h-4" />
            </button>
          </div>
        </div>
      </template>

      <!-- Batch Mode -->
      <template v-else-if="practiceMode === 'batch'">
        <!-- Score display -->
        <div v-if="batchSubmitted" class="mb-4 p-4 rounded-lg text-center bg-white border">
          <div
            class="text-2xl font-bold"
            :class="
              batchScorePercent >= 80
                ? 'text-green-600'
                : batchScorePercent >= 60
                  ? 'text-yellow-600'
                  : 'text-red-600'
            "
          >
            {{ batchScorePercent }}%
          </div>
          <button
            class="mt-2 px-3 py-1.5 text-sm text-purple-600 hover:text-purple-700"
            @click="resetBatch"
          >
            {{ t('wrongQuestionBook.retake') }}
          </button>
        </div>

        <!-- Grouped view -->
        <template v-if="groupedQuestions">
          <div v-for="(questions, type) in groupedQuestions" :key="type" class="mb-6">
            <h4 class="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
              <span
                class="px-2 py-0.5 text-xs rounded-full"
                :class="{
                  'bg-blue-50 text-blue-600': type === 'multiple_choice',
                  'bg-green-50 text-green-600': type === 'true_false',
                  'bg-orange-50 text-orange-600': type === 'fill_blank',
                  'bg-purple-50 text-purple-600': type === 'short_answer',
                }"
              >
                {{ getTypeLabel(type) }}
              </span>
              <span class="text-gray-500">{{ questions.length }}</span>
            </h4>
            <div class="space-y-3">
              <div
                v-for="(q, idx) in questions"
                :key="q.id"
                class="bg-white rounded-xl border border-gray-200"
              >
                <div class="p-4 border-b border-gray-100">
                  <div class="flex items-start gap-3">
                    <span
                      class="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full bg-purple-100 text-purple-700 text-xs font-medium"
                    >
                      {{ idx + 1 }}
                    </span>
                    <div class="flex-1 min-w-0">
                      <p
                        class="text-sm text-gray-800 font-medium leading-relaxed whitespace-pre-wrap"
                      >
                        {{ q.question }}
                      </p>
                      <span
                        class="inline-block mt-1.5 px-2 py-0.5 text-xs rounded-full"
                        :class="{
                          'bg-blue-50 text-blue-600': q.question_type === 'multiple_choice',
                          'bg-green-50 text-green-600': q.question_type === 'true_false',
                          'bg-orange-50 text-orange-600': q.question_type === 'fill_blank',
                          'bg-purple-50 text-purple-600': q.question_type === 'short_answer',
                        }"
                      >
                        {{ getTypeLabel(q.question_type) }}
                        {{ t('quiz.score', { text: getDefaultScore(q.question_type) }) }}
                      </span>
                    </div>
                    <button
                      class="flex-shrink-0 p-1.5 text-gray-400 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors"
                      @click="confirmDelete(q.id)"
                    >
                      <Delete class="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <!-- Options (multiple_choice / true_false) -->
                <div
                  v-if="q.question_type === 'multiple_choice' || q.question_type === 'true_false'"
                  class="p-4 space-y-2"
                >
                  <button
                    v-for="(option, optIndex) in q.options"
                    :key="optIndex"
                    class="w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all duration-150"
                    :class="{
                      'border-green-300 bg-green-100':
                        batchShowAnswers && option === q.correct_answer,
                      'border-red-300 bg-red-100':
                        batchShowAnswers &&
                        batchAnswers[q.id] === option &&
                        option !== q.correct_answer,
                      'border-blue-300 bg-blue-50':
                        !batchShowAnswers && batchAnswers[q.id] === option,
                      'border-gray-200 hover:border-purple-300 hover:bg-purple-50':
                        !batchShowAnswers && batchAnswers[q.id] !== option,
                      'border-gray-200 cursor-default':
                        batchSubmitted && batchAnswers[q.id] !== option,
                    }"
                    :disabled="batchSubmitted"
                    @click="batchAnswers[q.id] = option"
                  >
                    <span
                      class="flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center"
                      :class="{
                        'border-green-500 bg-green-500':
                          batchShowAnswers && option === q.correct_answer,
                        'border-red-500 bg-red-500':
                          batchShowAnswers &&
                          batchAnswers[q.id] === option &&
                          option !== q.correct_answer,
                        'border-blue-500 bg-blue-500':
                          !batchShowAnswers && batchAnswers[q.id] === option,
                        'border-gray-300': !batchShowAnswers && batchAnswers[q.id] !== option,
                        'border-gray-300 bg-gray-100':
                          batchSubmitted && batchAnswers[q.id] !== option,
                      }"
                    >
                      <span
                        v-if="!batchShowAnswers && batchAnswers[q.id] === option"
                        class="w-2 h-2 rounded-full bg-white"
                      />
                    </span>
                    <span
                      class="text-sm"
                      :class="{
                        'text-green-700 font-medium':
                          batchShowAnswers && option === q.correct_answer,
                        'text-red-700':
                          batchShowAnswers &&
                          batchAnswers[q.id] === option &&
                          option !== q.correct_answer,
                        'text-gray-700':
                          !batchShowAnswers ||
                          (batchAnswers[q.id] !== option && option !== q.correct_answer),
                      }"
                    >
                      {{ option }}
                    </span>
                  </button>
                </div>

                <!-- Fill blank / Short answer -->
                <div
                  v-if="q.question_type === 'fill_blank' || q.question_type === 'short_answer'"
                  class="p-4"
                >
                  <div v-if="!batchSubmitted">
                    <textarea
                      v-model="batchAnswers[q.id]"
                      class="w-full p-3 border border-gray-200 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-purple-300 focus:border-purple-300 transition-colors"
                      rows="3"
                      :placeholder="getPlaceholder(q.question_type)"
                    />
                  </div>
                  <div v-else class="space-y-3">
                    <div class="mb-3 p-3 bg-gray-50 border border-gray-200 rounded-lg">
                      <div class="text-xs text-gray-500 mb-1">{{ t('quiz.yourAnswer') }}</div>
                      <div class="text-sm text-gray-700 whitespace-pre-wrap">
                        {{ batchAnswers[q.id] || t('quiz.notAnswered') }}
                      </div>
                    </div>
                    <template v-if="batchEvaluationResults[String(q.id)]">
                      <div class="mb-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                        <div class="text-xs text-green-600 font-medium mb-1">
                          {{ t('quiz.referenceAnswer') }}
                        </div>
                        <div class="text-sm text-green-700">
                          {{ batchEvaluationResults[String(q.id)]!.standard_answer }}
                        </div>
                      </div>
                      <div
                        v-if="batchEvaluationResults[String(q.id)]!.total_score_included !== false"
                        class="mb-2 text-center"
                      >
                        <span
                          class="text-lg font-bold"
                          :class="
                            batchEvaluationResults[String(q.id)]!.score >= 5
                              ? 'text-green-600'
                              : 'text-red-600'
                          "
                        >
                          {{ batchEvaluationResults[String(q.id)]!.score }}
                        </span>
                        <span class="text-gray-400 text-sm">
                          / {{ getDefaultScore(q.question_type) }}
                        </span>
                      </div>
                      <div
                        v-if="batchEvaluationResults[String(q.id)]!.analysis"
                        class="p-3 bg-purple-50 border border-purple-100 rounded-lg"
                      >
                        <div class="text-xs text-purple-600 font-medium mb-1">
                          {{ t('quiz.analysisLabel') }}
                        </div>
                        <div class="text-sm text-gray-700 whitespace-pre-wrap">
                          {{ getAnalysisText(batchEvaluationResults[String(q.id)]!.analysis) }}
                        </div>
                      </div>
                    </template>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- Flat view -->
        <div v-else class="space-y-4">
          <div
            v-for="(q, idx) in wrongQuestions"
            :key="q.id"
            class="bg-white rounded-xl border border-gray-200"
          >
            <div class="p-4 border-b border-gray-100">
              <div class="flex items-start gap-3">
                <span
                  class="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full bg-purple-100 text-purple-700 text-xs font-medium"
                >
                  {{ idx + 1 }}
                </span>
                <div class="flex-1 min-w-0">
                  <p class="text-sm text-gray-800 font-medium leading-relaxed whitespace-pre-wrap">
                    {{ q.question }}
                  </p>
                  <span
                    class="inline-block mt-1.5 px-2 py-0.5 text-xs rounded-full"
                    :class="{
                      'bg-blue-50 text-blue-600': q.question_type === 'multiple_choice',
                      'bg-green-50 text-green-600': q.question_type === 'true_false',
                      'bg-orange-50 text-orange-600': q.question_type === 'fill_blank',
                      'bg-purple-50 text-purple-600': q.question_type === 'short_answer',
                    }"
                  >
                    {{ getTypeLabel(q.question_type) }}
                    {{ t('quiz.score', { text: getDefaultScore(q.question_type) }) }}
                  </span>
                </div>
                <button
                  class="flex-shrink-0 p-1.5 text-gray-400 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors"
                  @click="handleDelete(q.id)"
                >
                  <Delete class="w-4 h-4" />
                </button>
              </div>
            </div>

            <!-- Options -->
            <div
              v-if="q.question_type === 'multiple_choice' || q.question_type === 'true_false'"
              class="p-4 space-y-2"
            >
              <button
                v-for="(option, optIndex) in q.options"
                :key="optIndex"
                class="w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all duration-150"
                :class="{
                  'border-green-300 bg-green-100': batchShowAnswers && option === q.correct_answer,
                  'border-red-300 bg-red-100':
                    batchShowAnswers &&
                    batchAnswers[q.id] === option &&
                    option !== q.correct_answer,
                  'border-blue-300 bg-blue-50': !batchShowAnswers && batchAnswers[q.id] === option,
                  'border-gray-200 hover:border-purple-300 hover:bg-purple-50':
                    !batchShowAnswers && batchAnswers[q.id] !== option,
                  'border-gray-200 cursor-default': batchSubmitted && batchAnswers[q.id] !== option,
                }"
                :disabled="batchSubmitted"
                @click="batchAnswers[q.id] = option"
              >
                <span
                  class="flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center"
                  :class="{
                    'border-green-500 bg-green-500':
                      batchShowAnswers && option === q.correct_answer,
                    'border-red-500 bg-red-500':
                      batchShowAnswers &&
                      batchAnswers[q.id] === option &&
                      option !== q.correct_answer,
                    'border-blue-500 bg-blue-500':
                      !batchShowAnswers && batchAnswers[q.id] === option,
                    'border-gray-300': !batchShowAnswers && batchAnswers[q.id] !== option,
                    'border-gray-300 bg-gray-100': batchSubmitted && batchAnswers[q.id] !== option,
                  }"
                >
                  <span
                    v-if="!batchShowAnswers && batchAnswers[q.id] === option"
                    class="w-2 h-2 rounded-full bg-white"
                  />
                </span>
                <span
                  class="text-sm"
                  :class="{
                    'text-green-700 font-medium': batchShowAnswers && option === q.correct_answer,
                    'text-red-700':
                      batchShowAnswers &&
                      batchAnswers[q.id] === option &&
                      option !== q.correct_answer,
                    'text-gray-700':
                      !batchShowAnswers ||
                      (batchAnswers[q.id] !== option && option !== q.correct_answer),
                  }"
                >
                  {{ option }}
                </span>
              </button>
            </div>

            <!-- Fill blank / Short answer -->
            <div
              v-if="q.question_type === 'fill_blank' || q.question_type === 'short_answer'"
              class="p-4"
            >
              <div v-if="!batchSubmitted">
                <textarea
                  v-model="batchAnswers[q.id]"
                  class="w-full p-3 border border-gray-200 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-purple-300 focus:border-purple-300 transition-colors"
                  rows="3"
                  :placeholder="getPlaceholder(q.question_type)"
                />
              </div>
              <div v-else class="space-y-3">
                <div class="mb-3 p-3 bg-gray-50 border border-gray-200 rounded-lg">
                  <div class="text-xs text-gray-500 mb-1">{{ t('quiz.yourAnswer') }}</div>
                  <div class="text-sm text-gray-700 whitespace-pre-wrap">
                    {{ batchAnswers[q.id] || t('quiz.notAnswered') }}
                  </div>
                </div>
                <template v-if="batchEvaluationResults[String(q.id)]">
                  <div class="mb-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                    <div class="text-xs text-green-600 font-medium mb-1">
                      {{ t('quiz.referenceAnswer') }}
                    </div>
                    <div class="text-sm text-green-700">
                      {{ batchEvaluationResults[String(q.id)]!.standard_answer }}
                    </div>
                  </div>
                  <div
                    v-if="batchEvaluationResults[String(q.id)]!.total_score_included !== false"
                    class="mb-2 text-center"
                  >
                    <span
                      class="text-lg font-bold"
                      :class="
                        batchEvaluationResults[String(q.id)]!.score >= 5
                          ? 'text-green-600'
                          : 'text-red-600'
                      "
                    >
                      {{ batchEvaluationResults[String(q.id)]!.score }}
                    </span>
                    <span class="text-gray-400 text-sm">
                      / {{ getDefaultScore(q.question_type) }}
                    </span>
                  </div>
                  <div
                    v-if="batchEvaluationResults[String(q.id)]!.analysis"
                    class="p-3 bg-purple-50 border border-purple-100 rounded-lg"
                  >
                    <div class="text-xs text-purple-600 font-medium mb-1">
                      {{ t('quiz.analysisLabel') }}
                    </div>
                    <div class="text-sm text-gray-700 whitespace-pre-wrap">
                      {{ getAnalysisText(batchEvaluationResults[String(q.id)]!.analysis) }}
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </div>

        <!-- Submit button -->
        <div v-if="!batchSubmitted && wrongQuestions.length > 0" class="mt-4">
          <button
            class="w-full py-2.5 rounded-lg font-medium text-white transition-colors flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-700"
            :disabled="batchIsEvaluating"
            @click="submitBatch"
          >
            <Loader2 v-if="batchIsEvaluating" class="w-4 h-4 animate-spin" />
            {{ batchIsEvaluating ? t('quiz.aiGrading') : t('quiz.submitAnswers') }}
          </button>
        </div>
      </template>

      <!-- Delete confirmation modal -->
      <Teleport to="body">
        <Transition name="fade">
          <div
            v-if="showDeleteConfirm"
            class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
            @click.self="cancelDelete"
          >
            <div class="bg-white rounded-xl shadow-xl w-full max-w-sm mx-4 p-6">
              <div class="flex items-center gap-3 mb-4">
                <div class="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                  <Delete class="w-5 h-5 text-red-600" />
                </div>
                <h3 class="text-lg font-semibold text-gray-900">
                  {{ t('wrongQuestionBook.deleteConfirmTitle') }}
                </h3>
              </div>
              <p class="text-sm text-gray-600 mb-6">
                {{ t('wrongQuestionBook.deleteConfirmMessage') }}
              </p>
              <div class="flex gap-3">
                <button
                  class="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
                  @click="cancelDelete"
                >
                  {{ t('wrongQuestionBook.cancel') }}
                </button>
                <button
                  class="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                  @click="executeDelete"
                >
                  {{ t('wrongQuestionBook.delete') }}
                </button>
              </div>
            </div>
          </div>
        </Transition>
      </Teleport>
    </div>
  </div>
</template>
