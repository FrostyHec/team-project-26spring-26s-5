import { test, expect, type Page, type Route } from '@playwright/test'

const now = '2026-04-25T10:00:00Z'
const sessionId = 'sess-tree'

function sessionSummary() {
  return {
    id: sessionId,
    title: 'Tree Chat',
    created_at: now,
    updated_at: now,
    selected_provider_id: 'provider-1',
    fallback_mode: 'manual',
  }
}

function llmSettings() {
  return {
    temperature: 0,
    max_iterations: 10,
    system_prompt: 'You are a helpful assistant.',
    providers: [
      {
        id: 'provider-1',
        name: 'Primary Provider',
        priority: 0,
        base_url: 'https://example.test',
        api_key: 'secret',
        model: 'gpt-test',
        enabled: true,
      },
    ],
  }
}

function buildDetail(options?: {
  userId?: string
  userContent?: string
  assistantId?: string
  assistantContent?: string
  assistantStatus?: 'completed' | 'streaming'
  assistantNodeIds?: string[]
  selectedAssistantId?: string
  extraNodes?: Array<Record<string, unknown>>
  extraVersionGroups?: Array<Record<string, unknown>>
}) {
  const userId = options?.userId ?? 'u1'
  const assistantId = options?.assistantId ?? 'a1'
  const assistantNodeIds = options?.assistantNodeIds ?? [assistantId]
  const selectedAssistantId = options?.selectedAssistantId ?? assistantId
  const userContent = options?.userContent ?? 'Original question'
  const assistantContent = options?.assistantContent ?? 'Original answer'
  const assistantStatus = options?.assistantStatus ?? 'completed'

  return {
    session: sessionSummary(),
    messages: [
      {
        id: 1,
        session_id: sessionId,
        role: 'human',
        content: userContent,
        status: 'completed',
        created_at: now,
        ordinal: 0,
      },
      {
        id: 2,
        session_id: sessionId,
        role: 'ai',
        content: assistantContent,
        status: assistantStatus,
        created_at: now,
        ordinal: 1,
      },
    ],
    nodes: [
      {
        id: userId,
        session_id: sessionId,
        parent_id: null,
        role: 'human',
        content: userContent,
        status: 'completed',
        version_group_id: 'group-user',
        version_index: 0,
        source_kind: 'initial',
        source_node_id: null,
        response_to_node_id: null,
        created_at: now,
        updated_at: now,
      },
      {
        id: assistantId,
        session_id: sessionId,
        parent_id: userId,
        role: 'ai',
        content: assistantContent,
        status: assistantStatus,
        version_group_id: 'group-assistant',
        version_index: assistantNodeIds.indexOf(assistantId),
        source_kind: 'initial',
        source_node_id: null,
        response_to_node_id: userId,
        created_at: now,
        updated_at: now,
      },
      ...(options?.extraNodes ?? []),
    ],
    visible_path: [userId, assistantId],
    version_groups: [
      {
        version_group_id: 'group-assistant',
        node_ids: assistantNodeIds,
        selected_node_id: selectedAssistantId,
        position_in_path: 1,
      },
      ...(options?.extraVersionGroups ?? []),
    ],
  }
}

async function fulfillJson(route: Route, body: unknown) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

async function registerConversationTreeMocks(page: Page) {
  let currentDetail = buildDetail({
    assistantNodeIds: ['a1', 'a2'],
    extraNodes: [
      {
        id: 'a2',
        session_id: sessionId,
        parent_id: 'u1',
        role: 'ai',
        content: 'Alternative answer',
        status: 'completed',
        version_group_id: 'group-assistant',
        version_index: 1,
        source_kind: 'retry',
        source_node_id: 'a1',
        response_to_node_id: 'u1',
        created_at: now,
        updated_at: now,
      },
    ],
  })
  let pendingDetail: Record<string, unknown> | null = null
  let pendingToken = ''

  await page.route('**/api/health', (route) => fulfillJson(route, { status: 'ok' }))
  await page.route('**/api/skills', (route) => fulfillJson(route, []))
  await page.route('**/api/notifications/pending', (route) => fulfillJson(route, []))
  await page.route('**/api/settings', (route) => {
    if (route.request().method() === 'GET') {
      return fulfillJson(route, {
        cas_account: '',
        cas_password_is_set: false,
        email_account: '',
        email_password_is_set: false,
      })
    }
    return fulfillJson(route, {})
  })
  await page.route('**/api/settings/llm', (route) => fulfillJson(route, llmSettings()))
  await page.route('**/api/sessions', (route) => {
    if (route.request().method() === 'GET') {
      return fulfillJson(route, [sessionSummary()])
    }
    return fulfillJson(route, sessionSummary())
  })
  await page.route(`**/api/sessions/${sessionId}`, (route) => {
    if (route.request().method() === 'GET') {
      return fulfillJson(route, currentDetail)
    }
    return fulfillJson(route, sessionSummary())
  })
  await page.route(`**/api/sessions/${sessionId}/version-groups/group-assistant/select`, async (route) => {
    const body = route.request().postDataJSON() as { node_id: string }
    if (body.node_id === 'a2') {
      currentDetail = buildDetail({
        assistantId: 'a2',
        assistantContent: 'Alternative answer',
        assistantNodeIds: ['a1', 'a2'],
        selectedAssistantId: 'a2',
        extraNodes: [
          {
            id: 'a1',
            session_id: sessionId,
            parent_id: 'u1',
            role: 'ai',
            content: 'Original answer',
            status: 'completed',
            version_group_id: 'group-assistant',
            version_index: 0,
            source_kind: 'initial',
            source_node_id: null,
            response_to_node_id: 'u1',
            created_at: now,
            updated_at: now,
          },
        ],
      })
    }
    await fulfillJson(route, currentDetail)
  })
  await page.route(`**/api/sessions/${sessionId}/nodes/a2/edit`, async (route) => {
    const body = route.request().postDataJSON() as { content: string }
    currentDetail = buildDetail({
      assistantId: 'a3',
      assistantContent: body.content,
      assistantNodeIds: ['a1', 'a2', 'a3'],
      selectedAssistantId: 'a3',
      extraNodes: [
        {
          id: 'a1',
          session_id: sessionId,
          parent_id: 'u1',
          role: 'ai',
          content: 'Original answer',
          status: 'completed',
          version_group_id: 'group-assistant',
          version_index: 0,
          source_kind: 'initial',
          source_node_id: null,
          response_to_node_id: 'u1',
          created_at: now,
          updated_at: now,
        },
        {
          id: 'a2',
          session_id: sessionId,
          parent_id: 'u1',
          role: 'ai',
          content: 'Alternative answer',
          status: 'completed',
          version_group_id: 'group-assistant',
          version_index: 1,
          source_kind: 'retry',
          source_node_id: 'a1',
          response_to_node_id: 'u1',
          created_at: now,
          updated_at: now,
        },
      ],
    })
    await fulfillJson(route, currentDetail)
  })
  await page.route(`**/api/sessions/${sessionId}/nodes/a1/retry`, async (route) => {
    currentDetail = buildDetail({
      assistantId: 'a3',
      assistantContent: '',
      assistantStatus: 'streaming',
      assistantNodeIds: ['a1', 'a2', 'a3'],
      selectedAssistantId: 'a3',
      extraNodes: [
        {
          id: 'a2',
          session_id: sessionId,
          parent_id: 'u1',
          role: 'ai',
          content: 'Alternative answer',
          status: 'completed',
          version_group_id: 'group-assistant',
          version_index: 1,
          source_kind: 'retry',
          source_node_id: 'a1',
          response_to_node_id: 'u1',
          created_at: now,
          updated_at: now,
        },
      ],
    })
    pendingDetail = buildDetail({
      assistantId: 'a3',
      assistantContent: 'Retried answer',
      assistantNodeIds: ['a1', 'a2', 'a3'],
      selectedAssistantId: 'a3',
      extraNodes: [
        {
          id: 'a2',
          session_id: sessionId,
          parent_id: 'u1',
          role: 'ai',
          content: 'Alternative answer',
          status: 'completed',
          version_group_id: 'group-assistant',
          version_index: 1,
          source_kind: 'retry',
          source_node_id: 'a1',
          response_to_node_id: 'u1',
          created_at: now,
          updated_at: now,
        },
      ],
    })
    pendingToken = 'Retried answer'
    await fulfillJson(route, currentDetail)
  })
  await page.route(`**/api/sessions/${sessionId}/nodes/u1/edit`, async (route) => {
    const body = route.request().postDataJSON() as { content: string }
    currentDetail = {
      ...buildDetail({
        userId: 'u2',
        userContent: body.content,
        assistantId: 'a4',
        assistantContent: '',
        assistantStatus: 'streaming',
      }),
      nodes: [
        {
          id: 'u1',
          session_id: sessionId,
          parent_id: null,
          role: 'human',
          content: 'Original question',
          status: 'completed',
          version_group_id: 'group-user',
          version_index: 0,
          source_kind: 'initial',
          source_node_id: null,
          response_to_node_id: null,
          created_at: now,
          updated_at: now,
        },
        {
          id: 'u2',
          session_id: sessionId,
          parent_id: null,
          role: 'human',
          content: body.content,
          status: 'completed',
          version_group_id: 'group-user',
          version_index: 1,
          source_kind: 'user_edit',
          source_node_id: 'u1',
          response_to_node_id: null,
          created_at: now,
          updated_at: now,
        },
        {
          id: 'a4',
          session_id: sessionId,
          parent_id: 'u2',
          role: 'ai',
          content: '',
          status: 'streaming',
          version_group_id: 'group-assistant-branch',
          version_index: 0,
          source_kind: 'initial',
          source_node_id: null,
          response_to_node_id: 'u2',
          created_at: now,
          updated_at: now,
        },
      ],
      visible_path: ['u2', 'a4'],
      version_groups: [
        {
          version_group_id: 'group-user',
          node_ids: ['u1', 'u2'],
          selected_node_id: 'u2',
          position_in_path: 0,
        },
      ],
    }
    pendingDetail = buildDetail({
      userId: 'u2',
      userContent: body.content,
      assistantId: 'a4',
      assistantContent: 'Edited answer',
      assistantNodeIds: ['a4'],
      selectedAssistantId: 'a4',
      extraNodes: [
        {
          id: 'u1',
          session_id: sessionId,
          parent_id: null,
          role: 'human',
          content: 'Original question',
          status: 'completed',
          version_group_id: 'group-user',
          version_index: 0,
          source_kind: 'initial',
          source_node_id: null,
          response_to_node_id: null,
          created_at: now,
          updated_at: now,
        },
      ],
      extraVersionGroups: [
        {
          version_group_id: 'group-user',
          node_ids: ['u1', 'u2'],
          selected_node_id: 'u2',
          position_in_path: 0,
        },
      ],
    })
    pendingToken = 'Edited answer'
    await fulfillJson(route, currentDetail)
  })
  await page.route('**/api/chat/stream', async (route) => {
    const requestBody = route.request().postDataJSON() as { message: string }
    if (requestBody.message === '' && pendingDetail) {
      currentDetail = pendingDetail
    }
    const body = [
      'data: {"type":"loop_start"}',
      pendingToken ? `data: ${JSON.stringify({ type: 'token', content: pendingToken })}` : '',
      'data: {"type":"loop_end"}',
      'data: [DONE]',
      '',
    ]
      .filter(Boolean)
      .join('\n')

    pendingDetail = null
    pendingToken = ''

    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body,
    })
  })
}

async function openSeededConversation(page: Page) {
  await page.goto('/')
  await page.locator('aside').getByText('Tree Chat').click()
  await expect(page.getByText('Original question')).toBeVisible()
}

test.describe('Conversation Tree', () => {
  test.beforeEach(async ({ page }) => {
    await registerConversationTreeMocks(page)
  })

  test('switches versions and saves an assistant edit as a new version', async ({ page }) => {
    await openSeededConversation(page)

    await page.getByRole('button', { name: 'V2' }).click()
    await expect(page.getByText('Alternative answer')).toBeVisible()

    await page.getByRole('button', { name: /^Edit$/ }).nth(1).click()
    await page.locator('textarea.min-h-28').fill('Edited assistant answer')
    await page.getByRole('button', { name: 'Save' }).last().click()

    await expect(page.getByText('Edited assistant answer')).toBeVisible()
  })

  test('retries an assistant branch and shows the regenerated version', async ({ page }) => {
    await openSeededConversation(page)

    await page.getByRole('button', { name: 'Retry' }).click()
    await expect(page.getByText('Retried answer')).toBeVisible()
    await expect(page.getByRole('button', { name: 'V3' })).toBeVisible()
  })

  test('edits a user message and regenerates the assistant branch', async ({ page }) => {
    await openSeededConversation(page)

    await page.getByRole('button', { name: /^Edit$/ }).first().click()
    await page.locator('textarea.min-h-28').fill('Edited question')
    await page.getByRole('button', { name: 'Save' }).last().click()

    await expect(page.getByText('Edited question')).toBeVisible()
    await expect(page.getByText('Edited answer')).toBeVisible()
  })
})