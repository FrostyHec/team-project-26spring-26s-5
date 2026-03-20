<script setup lang="ts">
import { ref, nextTick, watch, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()
const inputText = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

onMounted(() => {
  chatStore.checkConnection()
})

async function handleSend() {
  if (!inputText.value.trim()) return
  const msg = inputText.value
  inputText.value = ''
  await chatStore.sendMessage(msg)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

// Auto-scroll to bottom when messages change
watch(
  () => chatStore.messages.length,
  async () => {
    await nextTick()
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  },
)
</script>

<template>
  <div class="chat-view">
    <!-- Connection status -->
    <div class="status-bar" :class="{ connected: chatStore.isConnected }">
      <span class="status-dot" />
      {{ chatStore.isConnected ? 'Connected' : 'Disconnected' }}
      <button v-if="!chatStore.isConnected" class="btn-retry" @click="chatStore.checkConnection">
        Retry
      </button>
      <button class="btn-clear" @click="chatStore.clearMessages">Clear</button>
    </div>

    <!-- Messages -->
    <div ref="messagesContainer" class="messages">
      <div v-if="chatStore.messages.length === 0" class="empty-state">
        <h2>ReAct Agent</h2>
        <p>Ask me to perform calculations or answer questions!</p>
      </div>

      <div v-for="msg in chatStore.messages" :key="msg.id" class="message" :class="msg.role">
        <div class="message-header">
          {{ msg.role === 'user' ? 'You' : 'Agent' }}
        </div>

        <!-- Linear ReAct Trace -->
        <details
          v-if="msg.traceSteps && msg.traceSteps.length > 0"
          class="trace-block"
          :open="msg.loopActive"
        >
          <summary class="trace-summary">
            {{ msg.loopActive ? '⏳ ReAct Loop Running...' : '🔍 ReAct Trace' }}
          </summary>
          <div class="trace-steps">
            <div v-for="(step, i) in msg.traceSteps" :key="i" class="trace-step" :class="step.type">
              <!-- Loop start -->
              <div v-if="step.type === 'loop_start'" class="step-label loop-boundary">
                ▶ ReAct loop started
              </div>

              <!-- Thinking -->
              <div v-else-if="step.type === 'thinking'" class="step-thinking">
                💭 <strong>Thinking:</strong> {{ step.content }}
              </div>

              <!-- Tool start -->
              <div v-else-if="step.type === 'tool_start'" class="step-tool-start">
                🔧 <strong>Tool Call:</strong> {{ step.name }}
                <code class="tool-args">{{ JSON.stringify(step.input) }}</code>
              </div>

              <!-- Tool end -->
              <div v-else-if="step.type === 'tool_end'" class="step-tool-end">
                ✅ <strong>Result:</strong>
                <code class="tool-result">{{ step.output }}</code>
              </div>

              <!-- Loop end -->
              <div v-else-if="step.type === 'loop_end'" class="step-label loop-boundary">
                ■ ReAct loop finished
              </div>
            </div>
          </div>
        </details>

        <!-- Message content -->
        <div class="message-content">{{ msg.content }}</div>
      </div>

      <div v-if="chatStore.isLoading" class="loading-indicator">
        <span class="dot-pulse" />
      </div>
    </div>

    <!-- Input area -->
    <div class="input-area">
      <textarea
        v-model="inputText"
        placeholder="Type your message..."
        rows="1"
        :disabled="chatStore.isLoading"
        @keydown="handleKeydown"
      />
      <button
        class="btn-send"
        :disabled="!inputText.trim() || chatStore.isLoading"
        @click="handleSend"
      >
        Send
      </button>
    </div>

    <!-- Error display -->
    <div v-if="chatStore.error" class="error-bar">
      {{ chatStore.error }}
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 800px;
  margin: 0 auto;
  font-family:
    system-ui,
    -apple-system,
    sans-serif;
}

.status-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #f5f5f5;
  border-bottom: 1px solid #e0e0e0;
  font-size: 13px;
  color: #666;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f44;
}

.status-bar.connected .status-dot {
  background: #4caf50;
}

.btn-retry,
.btn-clear {
  margin-left: auto;
  padding: 4px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  font-size: 12px;
}

.btn-clear {
  margin-left: 8px;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.empty-state {
  text-align: center;
  color: #999;
  margin-top: 20vh;
}

.empty-state h2 {
  font-size: 24px;
  margin-bottom: 8px;
}

.message {
  margin-bottom: 16px;
  padding: 12px 16px;
  border-radius: 12px;
  max-width: 85%;
}

.message.user {
  background: #007bff;
  color: white;
  margin-left: auto;
  border-bottom-right-radius: 4px;
}

.message.assistant {
  background: #f0f0f0;
  border-bottom-left-radius: 4px;
}

.message-header {
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 4px;
  opacity: 0.7;
  text-transform: uppercase;
}

.message-content {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
}

.tool-calls {
  margin-bottom: 8px;
}

.tool-call {
  background: #e8f4f8;
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 4px;
  font-size: 13px;
}

.tool-call summary {
  cursor: pointer;
  font-weight: 500;
}

.tool-detail {
  margin-top: 6px;
  padding-left: 20px;
}

.tool-detail code {
  background: #d4edda;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 12px;
}

.trace-block {
  margin-bottom: 8px;
  border: 1px solid #d0d7de;
  border-radius: 8px;
  overflow: hidden;
}

.trace-summary {
  cursor: pointer;
  padding: 8px 12px;
  background: #f6f8fa;
  font-weight: 500;
  font-size: 13px;
  user-select: none;
}

.trace-steps {
  padding: 8px 12px;
  border-top: 1px solid #d0d7de;
}

.trace-step {
  padding: 4px 0;
  font-size: 13px;
  line-height: 1.5;
  border-bottom: 1px solid #eef1f3;
}

.trace-step:last-child {
  border-bottom: none;
}

.step-label.loop-boundary {
  color: #586069;
  font-weight: 600;
  font-size: 12px;
}

.step-thinking {
  color: #6f42c1;
  padding-left: 4px;
}

.step-tool-start {
  padding-left: 4px;
}

.step-tool-end {
  padding-left: 4px;
}

.tool-args,
.tool-result {
  display: inline-block;
  background: #d4edda;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 12px;
  margin-left: 4px;
}

.loading-indicator {
  display: flex;
  justify-content: center;
  padding: 16px;
}

.dot-pulse {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #999;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 0.3;
  }
  50% {
    opacity: 1;
  }
}

.input-area {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #e0e0e0;
  background: white;
}

.input-area textarea {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #ddd;
  border-radius: 8px;
  resize: none;
  font-size: 14px;
  font-family: inherit;
  outline: none;
}

.input-area textarea:focus {
  border-color: #007bff;
}

.btn-send {
  padding: 10px 20px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
}

.btn-send:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.error-bar {
  padding: 8px 16px;
  background: #ffebee;
  color: #c62828;
  font-size: 13px;
}
</style>
