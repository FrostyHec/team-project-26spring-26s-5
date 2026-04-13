<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ChevronDown } from 'lucide-vue-next'
import type { TraceStep } from '@/stores/chatTypes'
import { TRACE_STEP_TYPES } from '@/stores/chatConstants'

const { t } = useI18n()

defineProps<{
  steps: TraceStep[]
  loopActive: boolean
}>()

/** Map a trace step type to its display icon. */
function traceIcon(step: TraceStep): string {
  switch (step.type) {
    case TRACE_STEP_TYPES.LOOP_START:
      return '▶'
    case TRACE_STEP_TYPES.THINKING:
      return '💭'
    case TRACE_STEP_TYPES.TOOL_START:
      return '🔧'
    case TRACE_STEP_TYPES.TOOL_END:
      return '✅'
    case TRACE_STEP_TYPES.LOOP_END:
      return '■'
    case TRACE_STEP_TYPES.APPROVAL_REQUEST:
      return '⚠️'
    case TRACE_STEP_TYPES.WIDGET_DISPLAY:
      return '📊'
    default:
      return '•'
  }
}
</script>

<template>
  <details
    class="group w-full max-w-3xl bg-gray-50/80 rounded-xl border border-gray-200 overflow-hidden"
    :open="loopActive"
  >
    <summary
      class="flex items-center gap-2 px-4 py-2.5 text-sm text-gray-600 hover:bg-gray-100 cursor-pointer select-none font-medium transition-colors"
    >
      <ChevronDown
        class="w-4 h-4 text-gray-400 group-open:rotate-180 transition-transform duration-200"
      />
      {{
        loopActive ? t('chat.trace.running') : t('chat.trace.completed', { count: steps.length })
      }}
    </summary>

    <div
      class="p-4 border-t border-gray-200 max-h-80 overflow-y-auto space-y-2 bg-white font-mono text-[13px]"
    >
      <div v-for="(step, k) in steps" :key="k" class="flex items-start gap-2">
        <span class="mt-0.5 text-base">{{ traceIcon(step) }}</span>
        <div class="flex-1 w-0">
          <template v-if="step.type === TRACE_STEP_TYPES.THINKING">
            <span class="text-gray-600 break-words">{{ step.content }}</span>
          </template>
          <template v-else-if="step.type === TRACE_STEP_TYPES.TOOL_START">
            <span class="font-bold text-gray-700">{{ t('chat.trace.call') }} </span>
            <span class="text-blue-600 font-semibold">{{ step.name }}</span>
            <pre
              class="mt-1 text-xs text-green-700 bg-gray-50 p-2 rounded-md border border-gray-100 overflow-x-auto"
              >{{ JSON.stringify(step.input, null, 2) }}</pre
            >
          </template>
          <template v-else-if="step.type === TRACE_STEP_TYPES.TOOL_END">
            <span class="font-bold text-gray-700">{{ t('chat.trace.result') }} </span>
            <div
              class="mt-1 text-xs text-gray-600 bg-gray-50 p-2 rounded-md border border-gray-100 max-h-32 overflow-y-auto whitespace-pre-wrap"
            >
              {{ step.output }}
            </div>
          </template>
          <template v-else-if="step.type === TRACE_STEP_TYPES.LOOP_START">
            <span class="text-blue-500 font-bold tracking-wider text-xs uppercase">{{
              t('chat.trace.loopStarted')
            }}</span>
          </template>
          <template v-else-if="step.type === TRACE_STEP_TYPES.LOOP_END">
            <span class="text-emerald-500 font-bold tracking-wider text-xs uppercase">{{
              t('chat.trace.loopFinished')
            }}</span>
          </template>
          <template v-else-if="step.type === TRACE_STEP_TYPES.APPROVAL_REQUEST">
            <span class="text-amber-600 font-bold">{{
              t('chat.trace.awaitingApproval', { name: step.name })
            }}</span>
          </template>
          <template v-else-if="step.type === TRACE_STEP_TYPES.WIDGET_DISPLAY">
            <span class="text-purple-600 font-bold">{{
              t('chat.trace.widgetTriggered', { type: step.widgetType })
            }}</span>
          </template>
        </div>
      </div>
    </div>
  </details>
</template>
