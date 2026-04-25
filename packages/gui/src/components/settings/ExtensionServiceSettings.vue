<script setup lang="ts">
import { ref, toRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronDown, GripVertical, Pencil, Plus, Trash2 } from 'lucide-vue-next'
import { FALLBACK_MODES, type FallbackMode } from '@/api/agent'
import { createDefaultLlmSettings, type LlmSettingsResponse } from '@/api/settings'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'
import SettingsErrorDialog from './SettingsErrorDialog.vue'
import {
  normalizeProviderIds,
  type LlmSettingsValidationIssue,
  validateLlmSettings,
} from './llmSettingsValidation'
import { useSettingsErrorDialog } from './useSettingsErrorDialog'

const { t } = useI18n()
const chatStore = useChatStore()
const settingsStore = useSettingsStore()

const errorDialog = useSettingsErrorDialog(toRef(settingsStore, 'error'), {
  defaultSummary: () => t('settings.saveErrorSummary'),
})
const {
  visible: errorDialogVisible,
  summary: errorDialogSummary,
  hint: errorDialogHint,
  items: errorDialogItems,
  close: closeErrorDialog,
} = errorDialog

const preferenceErrorDialog = useSettingsErrorDialog(toRef(chatStore, 'error'), {
  defaultSummary: () => t('settings.extension.preferenceSaveFailureSummary'),
})
const {
  visible: preferenceErrorDialogVisible,
  summary: preferenceErrorDialogSummary,
  hint: preferenceErrorDialogHint,
  items: preferenceErrorDialogItems,
  close: closePreferenceErrorDialog,
} = preferenceErrorDialog

const fallbackOptions: Array<{
  value: FallbackMode
  labelKey: string
  descriptionKey: string
}> = [
  {
    value: FALLBACK_MODES.MANUAL,
    labelKey: 'chat.fallbackManual',
    descriptionKey: 'settings.extension.fallbackManualDescription',
  },
  {
    value: FALLBACK_MODES.AUTO,
    labelKey: 'chat.fallbackAuto',
    descriptionKey: 'settings.extension.fallbackAutoDescription',
  },
]

function providerReference(
  issue: Extract<
    LlmSettingsValidationIssue,
    | { code: 'provider-id-duplicate' | 'provider-api-key-required' }
    | {
        code:
          | 'provider-base-url-required'
          | 'provider-model-required'
          | 'provider-priority-invalid'
          | 'provider-enabled-required'
      }
  >,
): string {
  if ('providerName' in issue && issue.providerName) {
    const providerId = 'providerId' in issue ? issue.providerId : ''
    return t('settings.extension.providerReferenceNamed', {
      index: issue.index + 1,
      name: issue.providerName,
      id: providerId,
    })
  }
  if ('providerId' in issue && issue.providerId) {
    return t('settings.extension.providerReferenceId', {
      index: issue.index + 1,
      id: issue.providerId,
    })
  }
  return t('settings.extension.providerReferenceUnnamed', {
    index: issue.index + 1,
  })
}

function formatValidationIssue(issue: LlmSettingsValidationIssue): string {
  switch (issue.code) {
    case 'provider-id-required':
      return t('settings.extension.providerIdRequired', {
        provider: t('settings.extension.providerReferenceUnnamed', {
          index: issue.index + 1,
        }),
      })
    case 'provider-id-duplicate':
      return t('settings.extension.providerIdDuplicate', {
        provider: providerReference(issue),
        id: issue.providerId,
      })
    case 'provider-api-key-required':
      return t('settings.extension.providerApiKeyRequired', {
        provider: providerReference(issue),
      })
    case 'provider-name-required':
      return t('settings.extension.providerNameRequired', {
        provider: t('settings.extension.providerReferenceUnnamed', {
          index: issue.index + 1,
        }),
      })
    case 'provider-base-url-required':
      return t('settings.extension.providerBaseUrlRequired', {
        provider: providerReference(issue),
      })
    case 'provider-model-required':
      return t('settings.extension.providerModelRequired', {
        provider: providerReference(issue),
      })
    case 'provider-priority-invalid':
      return t('settings.extension.providerPriorityInvalid', {
        provider: providerReference(issue),
      })
    case 'provider-enabled-required':
      return t('settings.extension.providerEnabledRequired', {
        provider: providerReference(issue),
      })
  }
}

function cloneSettings(value: LlmSettingsResponse): LlmSettingsResponse {
  const clonedValue = JSON.parse(JSON.stringify(value)) as LlmSettingsResponse
  clonedValue.providers = normalizeProviderIds(clonedValue.providers).sort(
    (left, right) => left.priority - right.priority,
  )
  syncProviderOrder(clonedValue.providers)
  return clonedValue
}

const form = ref<LlmSettingsResponse>(cloneSettings(settingsStore.llmSettings))
const expandedProviderId = ref<string | null>(null)
const draggingProviderId = ref<string | null>(null)

watch(
  () => settingsStore.llmSettings,
  (value) => {
    form.value = cloneSettings(value)
    expandedProviderId.value = null
  },
  { deep: true },
)

function syncProviderOrder(providers: LlmSettingsResponse['providers']): void {
  providers.forEach((provider, index) => {
    provider.priority = index
  })
}

function addProvider(): void {
  const nextIdNumber = form.value.providers.reduce((maxValue, provider) => {
    const match = /^provider_(\d+)$/.exec(provider.id)
    if (!match) return maxValue
    return Math.max(maxValue, Number(match[1]))
  }, 0)
  const nextPriority = form.value.providers.length
  form.value.providers.push({
    id: `provider_${nextIdNumber + 1}`,
    name: '',
    priority: nextPriority,
    base_url: '',
    api_key: '',
    model: '',
    enabled: true,
  })
  syncProviderOrder(form.value.providers)
  expandedProviderId.value = form.value.providers[form.value.providers.length - 1]?.id ?? null
}

function removeProvider(index: number): void {
  const removedProviderId = form.value.providers[index]?.id ?? null
  form.value.providers.splice(index, 1)
  syncProviderOrder(form.value.providers)
  if (expandedProviderId.value === removedProviderId) {
    expandedProviderId.value = null
  }
}

function removeProviderByReference(
  providerToRemove: LlmSettingsResponse['providers'][number],
): void {
  const providerIndex = form.value.providers.findIndex(
    (candidate) => candidate === providerToRemove,
  )
  if (providerIndex >= 0) {
    removeProvider(providerIndex)
  }
}

function providerRowKey(
  provider: LlmSettingsResponse['providers'][number],
  providerIndex: number,
): string {
  return `${provider.id || 'provider'}-${provider.priority}-${providerIndex}`
}

function toggleProviderEditor(providerId: string): void {
  expandedProviderId.value = expandedProviderId.value === providerId ? null : providerId
}

function isProviderExpanded(providerId: string): boolean {
  return expandedProviderId.value === providerId
}

function handleProviderDragStart(providerId: string): void {
  draggingProviderId.value = providerId
}

function moveProvider(providerId: string, targetProviderId: string): void {
  if (providerId === targetProviderId) {
    return
  }

  const providers = form.value.providers
  const fromIndex = providers.findIndex((provider) => provider.id === providerId)
  const toIndex = providers.findIndex((provider) => provider.id === targetProviderId)
  if (fromIndex < 0 || toIndex < 0) {
    return
  }

  const [movedProvider] = providers.splice(fromIndex, 1)
  if (!movedProvider) {
    return
  }
  providers.splice(toIndex, 0, movedProvider)
  syncProviderOrder(providers)
}

function handleProviderDrop(targetProviderId: string): void {
  if (!draggingProviderId.value) {
    return
  }
  moveProvider(draggingProviderId.value, targetProviderId)
  draggingProviderId.value = null
}

function handleProviderDragEnd(): void {
  draggingProviderId.value = null
}

async function handleSave(): Promise<void> {
  syncProviderOrder(form.value.providers)
  const validationIssues = validateLlmSettings(form.value)
  if (validationIssues.length > 0) {
    settingsStore.error = null
    errorDialog.open(validationIssues.map(formatValidationIssue), {
      summary: t('settings.extension.validationSummary'),
      hint: t('settings.extension.validationHint'),
    })
    return
  }

  await settingsStore.saveLlmSettings(form.value)
}

async function handleReset(): Promise<void> {
  await settingsStore.resetLlmSettingsToDefault()
  form.value = cloneSettings(settingsStore.llmSettings || createDefaultLlmSettings())
}

async function handleFallbackModeChange(mode: FallbackMode): Promise<void> {
  if (chatStore.fallbackMode === mode) {
    return
  }
  await chatStore.updateActiveSessionPreferences({ fallback_mode: mode })
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-base font-semibold text-gray-900 mb-1">
        {{ t('settings.extension.title') }}
      </h2>
      <p class="text-sm text-gray-500">{{ t('settings.extension.description') }}</p>
    </div>

    <div class="space-y-4">
      <div class="grid gap-4 md:grid-cols-2">
        <label class="space-y-2 text-sm text-gray-700">
          <span class="font-medium">{{ t('settings.extension.temperatureLabel') }}</span>
          <input
            v-model.number="form.temperature"
            type="number"
            min="0"
            max="2"
            step="0.1"
            class="w-full rounded-lg border border-gray-300 px-3 py-2"
          />
        </label>

        <label class="space-y-2 text-sm text-gray-700">
          <span class="font-medium">{{ t('settings.extension.maxIterationsLabel') }}</span>
          <input
            v-model.number="form.max_iterations"
            type="number"
            min="1"
            step="1"
            class="w-full rounded-lg border border-gray-300 px-3 py-2"
          />
        </label>
      </div>

      <label class="space-y-2 text-sm text-gray-700 block">
        <span class="font-medium">{{ t('settings.extension.systemPromptLabel') }}</span>
        <textarea
          v-model="form.system_prompt"
          rows="5"
          class="w-full rounded-lg border border-gray-300 px-3 py-2"
          :placeholder="t('settings.extension.systemPromptPlaceholder')"
        />
      </label>

      <label
        class="flex items-start gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-700"
      >
        <input v-model="form.debug_mode" type="checkbox" class="mt-1 rounded border-gray-300" />
        <span class="space-y-1">
          <span class="block font-medium">{{ t('settings.extension.debugModeLabel') }}</span>
          <span class="block text-sm text-gray-500">
            {{ t('settings.extension.debugModeDescription') }}
          </span>
        </span>
      </label>
    </div>

    <div class="space-y-4 rounded-xl border border-gray-200 p-4">
      <div>
        <h3 class="text-sm font-semibold text-gray-900">
          {{ t('settings.extension.preferencesTitle') }}
        </h3>
        <p class="text-sm text-gray-500">{{ t('settings.extension.preferencesDescription') }}</p>
      </div>

      <div class="space-y-3">
        <div>
          <h4 class="text-sm font-medium text-gray-900">
            {{ t('settings.extension.fallbackModeLabel') }}
          </h4>
          <p class="mt-1 text-sm text-gray-500">
            {{ t('settings.extension.fallbackModeDescription') }}
          </p>
        </div>

        <div class="grid gap-3 md:grid-cols-2">
          <button
            v-for="option in fallbackOptions"
            :key="option.value"
            :data-testid="`fallback-mode-${option.value}`"
            type="button"
            class="rounded-xl border px-4 py-3 text-left transition-colors"
            :class="
              chatStore.fallbackMode === option.value
                ? 'border-blue-300 bg-blue-50 text-blue-700'
                : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300 hover:bg-gray-50'
            "
            @click="handleFallbackModeChange(option.value)"
          >
            <div class="text-sm font-semibold">{{ t(option.labelKey) }}</div>
            <p
              class="mt-1 text-xs leading-5"
              :class="chatStore.fallbackMode === option.value ? 'text-blue-600' : 'text-gray-500'"
            >
              {{ t(option.descriptionKey) }}
            </p>
          </button>
        </div>

        <p class="text-xs text-gray-500">
          {{
            chatStore.activeSessionId
              ? t('settings.extension.preferencesScopeSession')
              : t('settings.extension.preferencesScopeNextSession')
          }}
        </p>
      </div>
    </div>

    <div class="space-y-4">
      <div class="flex items-center justify-between gap-4">
        <div>
          <h3 class="text-sm font-semibold text-gray-900">
            {{ t('settings.extension.providersTitle') }}
          </h3>
          <p class="text-sm text-gray-500">{{ t('settings.extension.providersDescription') }}</p>
        </div>
        <button
          type="button"
          class="inline-flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          @click="addProvider"
        >
          <Plus class="h-4 w-4" />
          {{ t('settings.extension.addProvider') }}
        </button>
      </div>

      <div
        v-if="form.providers.length === 0"
        class="rounded-lg bg-gray-50 px-4 py-6 text-sm text-gray-500"
      >
        {{ t('settings.extension.emptyProviders') }}
      </div>

      <p v-else class="text-xs text-gray-500">
        {{ t('settings.extension.reorderProvidersHint') }}
      </p>

      <div
        v-for="(provider, providerIndex) in form.providers"
        :key="providerRowKey(provider, providerIndex)"
        class="rounded-xl border p-4 transition-colors"
        :class="
          draggingProviderId === provider.id
            ? 'border-blue-300 bg-blue-50/50'
            : 'border-gray-200 bg-white'
        "
        @dragover.prevent
        @drop="handleProviderDrop(provider.id)"
      >
        <div class="flex flex-wrap items-center gap-3">
          <button
            type="button"
            class="inline-flex h-9 w-9 shrink-0 cursor-grab items-center justify-center rounded-full border border-dashed border-gray-300 text-gray-500 transition-colors hover:border-gray-400 hover:text-gray-700 active:cursor-grabbing"
            :aria-label="t('settings.extension.dragProvider')"
            draggable="true"
            @dragstart="handleProviderDragStart(provider.id)"
            @dragend="handleProviderDragEnd"
          >
            <GripVertical class="h-4 w-4" />
          </button>

          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <h4 class="text-sm font-semibold text-gray-900">
                {{ provider.name || t('settings.extension.unnamedProvider') }}
              </h4>
              <span
                class="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-500"
              >
                #{{ provider.priority + 1 }}
              </span>
            </div>
            <p class="mt-1 text-xs text-gray-500">
              {{ t('settings.extension.providerIdLabel') }}: {{ provider.id }}
            </p>
          </div>

          <label
            class="inline-flex items-center gap-2 rounded-full border border-gray-200 px-3 py-2 text-sm text-gray-700"
          >
            <input v-model="provider.enabled" type="checkbox" class="rounded border-gray-300" />
            <span class="font-medium">{{ t('settings.extension.enabledLabel') }}</span>
          </label>

          <button
            type="button"
            class="inline-flex items-center gap-2 rounded-full border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:border-gray-300 hover:bg-gray-50"
            @click="toggleProviderEditor(provider.id)"
          >
            <Pencil class="h-4 w-4" />
            {{
              isProviderExpanded(provider.id)
                ? t('settings.extension.collapseProvider')
                : t('settings.extension.editProvider')
            }}
            <ChevronDown
              class="h-4 w-4 transition-transform"
              :class="isProviderExpanded(provider.id) ? 'rotate-180' : ''"
            />
          </button>

          <button
            type="button"
            class="inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm text-red-600 transition-colors hover:bg-red-50"
            @click="removeProviderByReference(provider)"
          >
            <Trash2 class="h-4 w-4" />
            {{ t('common.remove') }}
          </button>
        </div>

        <div
          v-if="isProviderExpanded(provider.id)"
          class="mt-4 grid gap-4 border-t border-gray-100 pt-4 md:grid-cols-2"
        >
          <label class="space-y-2 text-sm text-gray-700">
            <span class="font-medium">{{ t('settings.extension.providerNameLabel') }}</span>
            <input
              v-model="provider.name"
              type="text"
              class="w-full rounded-lg border border-gray-300 px-3 py-2"
            />
          </label>

          <div class="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600">
            <span class="font-medium text-gray-700"
              >{{ t('settings.extension.priorityLabel') }}:</span
            >
            {{ provider.priority + 1 }}
            <p class="mt-1 text-xs text-gray-500">
              {{ t('settings.extension.providerPriorityAutoHint') }}
            </p>
          </div>

          <label class="space-y-2 text-sm text-gray-700 md:col-span-2">
            <span class="font-medium">{{ t('settings.extension.baseUrlLabel') }}</span>
            <input
              v-model="provider.base_url"
              type="text"
              class="w-full rounded-lg border border-gray-300 px-3 py-2"
            />
          </label>

          <label class="space-y-2 text-sm text-gray-700">
            <span class="font-medium">{{ t('settings.extension.modelLabel') }}</span>
            <input
              v-model="provider.model"
              type="text"
              class="w-full rounded-lg border border-gray-300 px-3 py-2"
            />
          </label>

          <label class="space-y-2 text-sm text-gray-700">
            <span class="font-medium">{{ t('settings.extension.apiKeyLabel') }}</span>
            <input
              v-model="provider.api_key"
              type="password"
              class="w-full rounded-lg border border-gray-300 px-3 py-2"
            />
          </label>

          <p class="text-xs text-gray-500 md:col-span-2">
            {{ t('settings.extension.providerCardHint') }}
          </p>
        </div>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-3">
      <button
        type="button"
        class="inline-flex items-center justify-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
        :disabled="settingsStore.isSaving"
        @click="handleSave"
      >
        {{ settingsStore.isSaving ? t('common.saving') : t('common.save') }}
      </button>

      <button
        type="button"
        class="inline-flex items-center justify-center rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
        :disabled="settingsStore.isSaving || settingsStore.isResetting"
        @click="handleReset"
      >
        {{ settingsStore.isResetting ? t('common.resetting') : t('common.reset') }}
      </button>

      <p v-if="settingsStore.successMessage" class="text-sm text-green-600">
        {{ settingsStore.successMessage }}
      </p>
    </div>

    <SettingsErrorDialog
      :visible="errorDialogVisible"
      :title="t('settings.saveErrorTitle')"
      :summary="errorDialogSummary"
      :hint="errorDialogHint"
      :items="errorDialogItems"
      @close="closeErrorDialog"
    />

    <SettingsErrorDialog
      :visible="preferenceErrorDialogVisible"
      :title="t('settings.saveErrorTitle')"
      :summary="preferenceErrorDialogSummary"
      :hint="preferenceErrorDialogHint"
      :items="preferenceErrorDialogItems"
      @close="closePreferenceErrorDialog"
    />
  </div>
</template>
