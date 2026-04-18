import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAlarmStore } from '../alarm'
import { ALARM_LEAD_TIMES, ALARM_CHANNELS, DEADLINE_PRIORITIES } from '../alarmConstants'
import type { AlarmSettings } from '@/api/alarm'

// Mock the alarm API module
vi.mock('@/api/alarm', () => ({
  getAlarmSettings: vi.fn(),
  updateAlarmSettings: vi.fn(),
  getPendingNotifications: vi.fn(),
  ackNotification: vi.fn(),
}))

import {
  getAlarmSettings,
  updateAlarmSettings,
  getPendingNotifications,
  ackNotification,
} from '@/api/alarm'

const mockGetAlarmSettings = vi.mocked(getAlarmSettings)
const mockUpdateAlarmSettings = vi.mocked(updateAlarmSettings)
const mockGetPendingNotifications = vi.mocked(getPendingNotifications)
const mockAckNotification = vi.mocked(ackNotification)

const PENDING_NOTIFICATION = {
  id: 'uuid-1',
  message: 'You have 1 upcoming deadline(s)',
  details: ['CS101 HW1 — 2026-04-15 14:00'],
  created_at: '2026-04-15T09:00:00+00:00',
}

describe('useAlarmStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  it('F1: fetchAlarmSettings updates settings state', async () => {
    mockGetAlarmSettings.mockResolvedValue({
      enabled: false,
      lead_times: ['week_1'],
      channels: ['email'],
      enabled_priorities: ['high'],
    })

    const store = useAlarmStore()
    await store.fetchAlarmSettings()

    expect(store.settings.enabled).toBe(false)
    expect(store.settings.lead_times).toEqual(['week_1'])
    expect(store.isLoading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('F2: saveAlarmSettings calls API and updates state', async () => {
    const newSettings: AlarmSettings = {
      enabled: true,
      lead_times: [ALARM_LEAD_TIMES.DAY_3],
      channels: [ALARM_CHANNELS.IN_APP],
      enabled_priorities: [
        DEADLINE_PRIORITIES.HIGH,
        DEADLINE_PRIORITIES.MEDIUM,
        DEADLINE_PRIORITIES.LOW,
      ],
    }
    mockUpdateAlarmSettings.mockResolvedValue(newSettings)

    const store = useAlarmStore()
    const ok = await store.saveAlarmSettings(newSettings)

    expect(ok).toBe(true)
    expect(mockUpdateAlarmSettings).toHaveBeenCalledWith(newSettings)
    expect(store.settings).toEqual(newSettings)
    expect(store.isSaving).toBe(false)
  })

  it('F3: fetchPendingNotifications sets showModal when items exist', async () => {
    mockGetPendingNotifications.mockResolvedValue([PENDING_NOTIFICATION])

    const store = useAlarmStore()
    await store.fetchPendingNotifications()

    expect(store.pendingNotifications).toHaveLength(1)
    expect(store.showModal).toBe(true)
  })

  it('F4: ackAll calls ackNotification for each id and clears state', async () => {
    mockGetPendingNotifications.mockResolvedValue([
      PENDING_NOTIFICATION,
      { ...PENDING_NOTIFICATION, id: 'uuid-2', message: 'msg2' },
    ])
    mockAckNotification.mockResolvedValue(undefined)

    const store = useAlarmStore()
    await store.fetchPendingNotifications()
    expect(store.pendingNotifications).toHaveLength(2)

    await store.ackAll()

    expect(mockAckNotification).toHaveBeenCalledTimes(2)
    expect(store.pendingNotifications).toHaveLength(0)
    expect(store.showModal).toBe(false)
  })

  it('F5: fetchAlarmSettings error sets store.error and clears isLoading', async () => {
    mockGetAlarmSettings.mockRejectedValue(new Error('Network error'))

    const store = useAlarmStore()
    await store.fetchAlarmSettings()

    expect(store.error).toBe('Network error')
    expect(store.isLoading).toBe(false)
  })

  it('F6: saveAlarmSettings error returns false and sets store.error', async () => {
    mockUpdateAlarmSettings.mockRejectedValue(new Error('Save failed'))

    const store = useAlarmStore()
    const ok = await store.saveAlarmSettings({
      enabled: true,
      lead_times: [ALARM_LEAD_TIMES.DAY_1],
      channels: [ALARM_CHANNELS.IN_APP],
      enabled_priorities: [DEADLINE_PRIORITIES.HIGH],
    })

    expect(ok).toBe(false)
    expect(store.error).toBe('Save failed')
    expect(store.isSaving).toBe(false)
  })

  it('F7: dismissModal sets showModal to false without clearing notifications', async () => {
    mockGetPendingNotifications.mockResolvedValue([PENDING_NOTIFICATION])

    const store = useAlarmStore()
    await store.fetchPendingNotifications()
    expect(store.showModal).toBe(true)

    store.dismissModal()

    expect(store.showModal).toBe(false)
    expect(store.pendingNotifications).toHaveLength(1)
  })

  it('F8: fetchPendingNotifications with empty list leaves showModal false', async () => {
    mockGetPendingNotifications.mockResolvedValue([])

    const store = useAlarmStore()
    await store.fetchPendingNotifications()

    expect(store.pendingNotifications).toHaveLength(0)
    expect(store.showModal).toBe(false)
  })
})
