/**
 * API client for user profile settings.
 * Communicates with the backend ``/settings`` endpoint.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

/** The settings API endpoint path. */
const SETTINGS_ENDPOINT = `${API_BASE}/settings`
const LLM_SETTINGS_ENDPOINT = `${SETTINGS_ENDPOINT}/llm`

interface ApiErrorDetailItem {
  msg?: string
}

async function buildApiError(response: Response, fallbackMessage: string): Promise<Error> {
  let detailMessage = ''

  try {
    const payload = (await response.json()) as { detail?: string | ApiErrorDetailItem[] }
    const detail = payload.detail
    if (typeof detail === 'string') {
      detailMessage = detail
    } else if (Array.isArray(detail)) {
      detailMessage = detail
        .map((item) => item.msg?.replace(/^Value error,\s*/, '').trim() ?? '')
        .filter(Boolean)
        .join('\n')
    }
  } catch {
    // Fall back to the generic message when the response body is not JSON.
  }

  if (detailMessage) {
    return new Error(detailMessage)
  }

  return new Error(`${fallbackMessage}: ${response.status}`)
}

/** Sanitised settings response from the backend.
 *
 * Passwords are never returned — only a boolean flag indicates
 * whether each password has been configured.
 */
export interface SettingsResponse {
  cas_account: string
  cas_password_is_set: boolean
  email_account: string
  email_password_is_set: boolean
}

/** Partial update request body for PUT /settings.
 *
 * All fields are optional; only supplied (non-null) fields are modified.
 * Send an empty string for a password field to clear it.
 */
export interface UpdateSettingsRequest {
  cas_account?: string | null
  cas_password?: string | null
  email_account?: string | null
  email_password?: string | null
}

export interface LlmProviderSettings {
  id: string
  name: string
  priority: number
  base_url: string
  api_key: string
  model: string
  enabled: boolean
}

export interface LlmSettingsResponse {
  temperature: number
  max_iterations: number
  system_prompt: string
  debug_mode: boolean
  providers: LlmProviderSettings[]
}

export type UpdateLlmSettingsRequest = LlmSettingsResponse

export function createDefaultLlmSettings(): LlmSettingsResponse {
  return {
    temperature: 0,
    max_iterations: 10,
    system_prompt:
      'You are a helpful AI assistant. You can use tools to help answer questions. When you need to perform calculations, use the available calculator tools.',
    debug_mode: false,
    providers: [],
  }
}

/**
 * Fetch the current user settings from the backend.
 *
 * @returns Sanitised settings response (passwords never included).
 * @throws Error on network or server error.
 */
export async function getSettings(): Promise<SettingsResponse> {
  const response = await fetch(SETTINGS_ENDPOINT, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })

  if (!response.ok) {
    throw await buildApiError(response, 'Failed to fetch settings')
  }

  return (await response.json()) as SettingsResponse
}

/**
 * Update user settings via the backend.
 *
 * Only non-null fields in the request are applied on the backend.
 *
 * @param request - Partial update with plaintext credentials.
 * @returns The updated sanitised settings response.
 * @throws Error on network or server error.
 */
export async function updateSettings(request: UpdateSettingsRequest): Promise<SettingsResponse> {
  const response = await fetch(SETTINGS_ENDPOINT, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    throw await buildApiError(response, 'Failed to update settings')
  }

  return (await response.json()) as SettingsResponse
}

/**
 * Reset all user settings to their initial (empty) state.
 *
 * @returns The sanitised settings response after reset (all fields cleared).
 * @throws Error on network or server error.
 */
export async function resetSettings(): Promise<SettingsResponse> {
  const response = await fetch(SETTINGS_ENDPOINT, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
  })

  if (!response.ok) {
    throw await buildApiError(response, 'Failed to reset settings')
  }

  return (await response.json()) as SettingsResponse
}

export async function getLlmSettings(): Promise<LlmSettingsResponse> {
  const response = await fetch(LLM_SETTINGS_ENDPOINT, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })

  if (!response.ok) {
    throw await buildApiError(response, 'Failed to fetch LLM settings')
  }

  return (await response.json()) as LlmSettingsResponse
}

export async function updateLlmSettings(
  request: UpdateLlmSettingsRequest,
): Promise<LlmSettingsResponse> {
  const response = await fetch(LLM_SETTINGS_ENDPOINT, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    throw await buildApiError(response, 'Failed to update LLM settings')
  }

  return (await response.json()) as LlmSettingsResponse
}

export async function resetLlmSettings(): Promise<LlmSettingsResponse> {
  const response = await fetch(LLM_SETTINGS_ENDPOINT, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
  })

  if (!response.ok) {
    throw await buildApiError(response, 'Failed to reset LLM settings')
  }

  return (await response.json()) as LlmSettingsResponse
}
