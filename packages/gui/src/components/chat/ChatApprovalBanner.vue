<script setup lang="ts">
import { AlertCircle } from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()
</script>

<template>
  <div
    v-if="chatStore.pendingApproval"
    class="mx-4 mb-2 p-4 bg-amber-50 border border-amber-200 rounded-xl shadow-lg"
  >
    <div class="flex items-start gap-3">
      <AlertCircle class="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
      <div class="flex-1">
        <h4 class="text-sm font-semibold text-gray-800 mb-1">Tool Approval Required</h4>
        <p class="text-xs text-gray-600 mb-2">
          <strong>{{ chatStore.pendingApproval.toolName }}</strong>
        </p>
        <code
          class="block text-xs bg-white p-2 rounded border border-amber-100 mb-3 max-h-20 overflow-auto"
        >
          {{ JSON.stringify(chatStore.pendingApproval.toolArgs, null, 2) }}
        </code>
        <div class="flex gap-2">
          <button
            class="px-3 py-1.5 bg-green-600 text-white text-xs rounded-lg hover:bg-green-700 transition-colors"
            @click="chatStore.respondToApproval(true)"
          >
            ✅ Approve
          </button>
          <button
            class="px-3 py-1.5 bg-red-600 text-white text-xs rounded-lg hover:bg-red-700 transition-colors"
            @click="chatStore.respondToApproval(false)"
          >
            ❌ Reject
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
