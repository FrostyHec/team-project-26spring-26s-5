<script setup lang="ts">
import { CheckCircle2, Loader2, AlertCircle } from 'lucide-vue-next'
import type { ToolCallInfo } from '@/stores/chatTypes'
import { TOOL_CALL_STATUS } from '@/stores/chatConstants'

defineProps<{
  toolCalls: ToolCallInfo[]
}>()
</script>

<template>
  <div class="flex flex-wrap gap-2">
    <div
      v-for="(tc, j) in toolCalls"
      :key="j"
      class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-50 border border-gray-100 rounded-full text-xs font-medium text-gray-500 shadow-sm"
    >
      <CheckCircle2
        v-if="tc.status === TOOL_CALL_STATUS.COMPLETED"
        class="w-3.5 h-3.5 text-green-500"
      />
      <Loader2
        v-else-if="tc.status === TOOL_CALL_STATUS.RUNNING"
        class="w-3.5 h-3.5 text-blue-500 animate-spin"
      />
      <AlertCircle v-else class="w-3.5 h-3.5 text-red-500" />
      <span>{{ tc.name }}</span>
    </div>
  </div>
</template>
