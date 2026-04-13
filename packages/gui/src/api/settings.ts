/**
 * API client for user profile settings.
 * Communicates with the backend ``/settings`` endpoint.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

/** The settings API endpoint path. */
const SETTINGS_ENDPOINT = `${API_BASE}/settings`

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
    throw new Error(`Failed to fetch settings: ${response.status}`)
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
    throw new Error(`Failed to update settings: ${response.status}`)
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
    throw new Error(`Failed to reset settings: ${response.status}`)
  }

  return (await response.json()) as SettingsResponse
}
