/**
 * DeadlinePanelWidget filter tests — T1 through T9.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'
import enMessages from '@/i18n/locales/en.json'
import DeadlinePanelWidget from '../DeadlinePanelWidget.vue'
import { DateType, type DeadlineInfo } from '@/api/agent'
import * as agentApi from '@/api/agent'

// ── Mock setup ───────────────────────────────────────────────────

vi.mock('@/api/agent', async (importOriginal) => {
  const actual = await importOriginal<typeof agentApi>()
  return {
    ...actual,
    fetchDeadlines: vi.fn(),
    toggleDeadlineComplete: vi.fn().mockResolvedValue(undefined),
  }
})

const mockFetchDeadlines = vi.mocked(agentApi.fetchDeadlines)

function makeTask(overrides: Partial<DeadlineInfo> = {}): DeadlineInfo {
  return {
    id: crypto.randomUUID(),
    title: 'Test Task',
    course: '',
    due_date: '2026-05-01',
    priority: 'medium',
    source: 'manual',
    description: '',
    date_type: DateType.MOMENT_DAY,
    start_date: '',
    completed: false,
    ...overrides,
  }
}

const TASKS: DeadlineInfo[] = [
  makeTask({ id: '1', title: 'CS302 High', course: 'CS302', priority: 'high' }),
  makeTask({ id: '2', title: 'CS302 Low', course: 'CS302', priority: 'low' }),
  makeTask({ id: '3', title: 'MATH201 Med', course: 'MATH201', priority: 'medium' }),
  makeTask({ id: '4', title: 'No Course', course: '', priority: 'high' }),
]

const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })

async function mountWidget(tasks: DeadlineInfo[] = TASKS) {
  mockFetchDeadlines.mockResolvedValue(tasks)
  const wrapper = mount(DeadlinePanelWidget, {
    global: { plugins: [i18n, createPinia()] },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

// ── Tests ─────────────────────────────────────────────────────────

describe('DeadlinePanelWidget — filter controls', () => {
  // T1
  it('renders course dropdown with unique sorted courses', async () => {
    const wrapper = await mountWidget()
    const options = wrapper
      .find('[data-testid="filter-course"]')
      .findAll('option')
      .map((o) => o.text())
    expect(options[0]).toBe('All courses')
    expect(options).toContain('CS302')
    expect(options).toContain('MATH201')
    // no empty-string course in the dropdown
    expect(options.filter((o) => o === '')).toHaveLength(0)
    // sorted: CS302 < MATH201
    const idx302 = options.indexOf('CS302')
    const idxMath = options.indexOf('MATH201')
    expect(idx302).toBeLessThan(idxMath)
  })

  // T2
  it('renders priority dropdown with all 4 options', async () => {
    const wrapper = await mountWidget()
    const options = wrapper
      .find('[data-testid="filter-priority"]')
      .findAll('option')
      .map((o) => o.text())
    expect(options).toHaveLength(4)
    expect(options[0]).toBe('All')
    expect(options).toContain('High')
    expect(options).toContain('Medium')
    expect(options).toContain('Low')
  })

  // T3
  it('filter by course CS302 shows only CS302 tasks', async () => {
    const wrapper = await mountWidget()
    await wrapper.find('[data-testid="filter-course"]').setValue('CS302')
    const titles = wrapper.findAll('[data-testid="task-title"]').map((w) => w.text().trim())
    expect(titles).toContain('CS302 High')
    expect(titles).toContain('CS302 Low')
    expect(titles).not.toContain('MATH201 Med')
    expect(titles).not.toContain('No Course')
  })

  // T4
  it('filter by priority HIGH shows only high tasks', async () => {
    const wrapper = await mountWidget()
    await wrapper.find('[data-testid="filter-priority"]').setValue('high')
    const titles = wrapper.findAll('[data-testid="task-title"]').map((w) => w.text().trim())
    expect(titles).toContain('CS302 High')
    expect(titles).toContain('No Course')
    expect(titles).not.toContain('CS302 Low')
    expect(titles).not.toContain('MATH201 Med')
  })

  // T5
  it('combined filter CS302 + HIGH shows single task', async () => {
    const wrapper = await mountWidget()
    await wrapper.find('[data-testid="filter-course"]').setValue('CS302')
    await wrapper.find('[data-testid="filter-priority"]').setValue('high')
    const titles = wrapper.findAll('[data-testid="task-title"]').map((w) => w.text().trim())
    expect(titles).toEqual(['CS302 High'])
  })

  // T6
  it('empty filter result shows no-match message', async () => {
    const wrapper = await mountWidget()
    // MATH201 has only medium priority — selecting high yields no match
    await wrapper.find('[data-testid="filter-course"]').setValue('MATH201')
    await wrapper.find('[data-testid="filter-priority"]').setValue('high')
    expect(wrapper.find('[data-testid="filter-no-match"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="filter-no-match"]').text()).toContain(
      'No deadlines match current filters.',
    )
  })

  // T7
  it('reset course to All shows all tasks again', async () => {
    const wrapper = await mountWidget()
    await wrapper.find('[data-testid="filter-course"]').setValue('CS302')
    expect(wrapper.findAll('[data-testid="task-title"]')).toHaveLength(2)
    await wrapper.find('[data-testid="filter-course"]').setValue('')
    expect(wrapper.findAll('[data-testid="task-title"]')).toHaveLength(4)
  })

  // T8
  it('filter combined with hideCompleted hides completed tasks', async () => {
    const tasks = [
      makeTask({ id: '10', title: 'CS302 Active', course: 'CS302', completed: false }),
      makeTask({ id: '11', title: 'CS302 Done', course: 'CS302', completed: true }),
    ]
    const wrapper = await mountWidget(tasks)
    await wrapper.find('[data-testid="filter-course"]').setValue('CS302')
    const hideCheckbox = wrapper.find('input[type="checkbox"]')
    await hideCheckbox.setValue(true)
    const titles = wrapper.findAll('[data-testid="task-title"]').map((w) => w.text().trim())
    expect(titles).toContain('CS302 Active')
    expect(titles).not.toContain('CS302 Done')
  })

  // T9
  it('course dropdown resets when loaded data no longer contains selected course', async () => {
    const wrapper = await mountWidget()
    await wrapper.find('[data-testid="filter-course"]').setValue('CS302')

    // Simulate reload: new data only has MATH201
    const newTasks = [makeTask({ id: '99', title: 'New Task', course: 'MATH201' })]
    mockFetchDeadlines.mockResolvedValue(newTasks)
    // Trigger the reload via the refresh button
    await wrapper.find('button[title="Refresh"]').trigger('click')
    await flushPromises()

    // Course dropdown should have reset (CS302 no longer in data)
    const courseSelect = wrapper.find('[data-testid="filter-course"]')
    expect((courseSelect.element as HTMLSelectElement).value).toBe('')
  })
})
