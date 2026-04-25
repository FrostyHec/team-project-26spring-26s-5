import { ref, watch, type Ref } from 'vue'

interface SettingsErrorDialogOptions {
  summary?: string
  hint?: string
}

interface UseSettingsErrorDialogOptions {
  defaultSummary?: () => string
  defaultHint?: () => string
}

export function splitSettingsErrorItems(message: string): string[] {
  return message
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
}

export function useSettingsErrorDialog(
  errorState: Ref<string | null>,
  options: UseSettingsErrorDialogOptions = {},
) {
  const visible = ref(false)
  const summary = ref('')
  const hint = ref('')
  const items = ref<string[]>([])

  function open(nextItems: string[], overrides: SettingsErrorDialogOptions = {}): void {
    items.value = nextItems
    summary.value = overrides.summary ?? options.defaultSummary?.() ?? ''
    hint.value = overrides.hint ?? options.defaultHint?.() ?? ''
    visible.value = nextItems.length > 0
  }

  function openFromMessage(message: string, overrides: SettingsErrorDialogOptions = {}): void {
    open(splitSettingsErrorItems(message), overrides)
  }

  function close(): void {
    visible.value = false
    summary.value = ''
    hint.value = ''
    items.value = []
    errorState.value = null
  }

  watch(errorState, (errorMessage) => {
    if (!errorMessage) {
      return
    }
    openFromMessage(errorMessage)
  })

  return {
    visible,
    summary,
    hint,
    items,
    open,
    openFromMessage,
    close,
  }
}
