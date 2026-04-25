import { describe, expect, it } from 'vitest'
import { nextTick, ref } from 'vue'
import { splitSettingsErrorItems, useSettingsErrorDialog } from '../useSettingsErrorDialog'

describe('useSettingsErrorDialog', () => {
  it('splits multiline backend errors into dialog items', () => {
    expect(splitSettingsErrorItems(' first issue \n\n second issue ')).toEqual([
      'first issue',
      'second issue',
    ])
  })

  it('opens from watched store errors with default summary', async () => {
    const error = ref<string | null>(null)
    const dialog = useSettingsErrorDialog(error, {
      defaultSummary: () => 'default summary',
    })

    error.value = 'missing api key\nduplicate provider id'
    await nextTick()

    expect(dialog.visible.value).toBe(true)
    expect(dialog.summary.value).toBe('default summary')
    expect(dialog.items.value).toEqual(['missing api key', 'duplicate provider id'])

    dialog.close()

    expect(dialog.visible.value).toBe(false)
    expect(error.value).toBeNull()
  })
})
