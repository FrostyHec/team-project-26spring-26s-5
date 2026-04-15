/**
 * API client for the email feature.
 * Communicates with the backend ``/email`` endpoints.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'
const EMAIL_ENDPOINT = `${API_BASE}/email`
const CREDENTIALS_MISSING_CODE = 'EMAIL_CREDENTIALS_MISSING'

interface ApiErrorPayload {
  detail?:
    | string
    | {
        code?: string
        message?: string
      }
}

async function buildApiError(response: Response, fallback: string): Promise<Error> {
  let detailMessage = ''
  let detailCode = ''

  try {
    const payload = (await response.json()) as ApiErrorPayload
    if (typeof payload.detail === 'string') {
      detailMessage = payload.detail
    } else if (payload.detail && typeof payload.detail === 'object') {
      detailCode = payload.detail.code ?? ''
      detailMessage = payload.detail.message ?? ''
    }
  } catch {
    // ignore non-JSON error bodies
  }

  if (detailMessage) {
    if (detailCode) {
      return new Error(`${fallback} [${detailCode}]: ${detailMessage}`)
    }
    return new Error(`${fallback}: ${detailMessage}`)
  }

  if (response.status === 428) {
    return new Error(`${fallback} [${CREDENTIALS_MISSING_CODE}]`)
  }

  return new Error(`${fallback}: ${response.status}`)
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Lightweight email summary for list display. */
export interface EmailSummary {
  uid: number
  subject: string
  sender: string
  sender_name: string
  date: string
  preview: string
  is_seen: boolean
  is_flagged: boolean
  is_answered: boolean
  has_attachments: boolean
}

/** Attachment metadata. */
export interface AttachmentInfo {
  id: number
  email_uid: number
  filename: string
  content_type: string
  content_id: string
  local_path: string
  file_size: number
  download_time: string
  is_downloaded: boolean
}

/** Full email detail. */
export interface EmailDetail {
  uid: number
  message_id: string
  subject: string
  sender: string
  sender_name: string
  recipients: string
  cc: string
  date: string
  body_text: string
  html_local_path: string
  is_seen: boolean
  is_flagged: boolean
  is_answered: boolean
  has_attachments: boolean
  attachments: AttachmentInfo[]
}

/** Send email request body. */
export interface SendEmailRequest {
  to: string
  cc?: string
  subject: string
  html_body?: string
  plain_body?: string
  in_reply_to?: string
  references?: string
  attachment_paths?: string[]
}

/** Sync result from the backend. */
export interface EmailSyncResult {
  new_count: number
  updated_count: number
  total_count: number
  synced_at: string
}

/** Connection test result. */
export interface EmailConnectionTestResult {
  success: boolean
  message: string
  imap_ok: boolean
  smtp_ok: boolean
}

/** Email-specific settings. */
export interface EmailSettingsInfo {
  email_fetch_days: number
  auto_sync: boolean
}

/** Cache clear result. */
export interface ClearCacheResult {
  cleared_files: number
  cleared_bytes: number
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/** Sync (pull) new emails from the mail server. */
export async function syncEmails(days?: number, folder?: string): Promise<EmailSyncResult> {
  const params = new URLSearchParams()
  if (days != null) params.set('days', String(days))
  if (folder) params.set('folder', folder)
  const qs = params.toString()
  const response = await fetch(`${EMAIL_ENDPOINT}/sync${qs ? `?${qs}` : ''}`, {
    method: 'POST',
  })
  if (!response.ok) throw await buildApiError(response, 'Sync failed')
  return (await response.json()) as EmailSyncResult
}

/** List email summaries with pagination and filters. */
export async function listEmails(options?: {
  limit?: number
  offset?: number
  flagged_only?: boolean
  unseen_only?: boolean
  folder?: string
}): Promise<EmailSummary[]> {
  const params = new URLSearchParams()
  if (options?.limit != null) params.set('limit', String(options.limit))
  if (options?.offset != null) params.set('offset', String(options.offset))
  if (options?.flagged_only) params.set('flagged_only', 'true')
  if (options?.unseen_only) params.set('unseen_only', 'true')
  if (options?.folder) params.set('folder', options.folder)

  const qs = params.toString()
  const response = await fetch(`${EMAIL_ENDPOINT}${qs ? `?${qs}` : ''}`)
  if (!response.ok) throw await buildApiError(response, 'List emails failed')
  return (await response.json()) as EmailSummary[]
}

/** Get email count. */
export async function countEmails(): Promise<number> {
  const response = await fetch(`${EMAIL_ENDPOINT}/count`)
  if (!response.ok) throw await buildApiError(response, 'Count failed')
  const data = (await response.json()) as { total: number }
  return data.total
}

/** Get full email detail by UID. */
export async function getEmailDetail(uid: number, folder: string = 'INBOX'): Promise<EmailDetail> {
  const params = new URLSearchParams({ folder })
  const response = await fetch(`${EMAIL_ENDPOINT}/${uid}?${params}`)
  if (!response.ok) throw await buildApiError(response, 'Get email failed')
  return (await response.json()) as EmailDetail
}

/** Get the URL for the cached HTML body. */
export function getEmailHtmlUrl(uid: number): string {
  return `${EMAIL_ENDPOINT}/${uid}/html`
}

/** Get the URL for downloading an attachment. */
export function getAttachmentUrl(uid: number, attachmentId: number): string {
  return `${EMAIL_ENDPOINT}/${uid}/attachments/${attachmentId}`
}

/** Trigger on-demand download of a regular attachment. */
export async function downloadAttachment(uid: number, attId: number): Promise<AttachmentInfo> {
  const response = await fetch(`${EMAIL_ENDPOINT}/${uid}/attachments/${attId}/download`, {
    method: 'POST',
  })
  if (!response.ok) throw await buildApiError(response, 'Download failed')
  return (await response.json()) as AttachmentInfo
}

/** Update an email flag. */
export async function updateEmailFlag(
  uid: number,
  flag: 'seen' | 'flagged' | 'answered' | 'deleted' | 'spam',
  value: boolean,
  folder: string = 'INBOX',
): Promise<{ success: boolean }> {
  const params = new URLSearchParams({ folder })
  const response = await fetch(`${EMAIL_ENDPOINT}/${uid}/flags?${params}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ flag, value }),
  })
  if (!response.ok) throw await buildApiError(response, 'Update flag failed')
  return (await response.json()) as { success: boolean }
}

/** Send an email. */
export async function sendEmail(request: SendEmailRequest): Promise<void> {
  const response = await fetch(`${EMAIL_ENDPOINT}/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!response.ok) throw await buildApiError(response, 'Send email failed')
}

/** Test IMAP/SMTP connection. */
export async function testEmailConnection(): Promise<EmailConnectionTestResult> {
  const response = await fetch(`${EMAIL_ENDPOINT}/test-connection`, {
    method: 'POST',
  })
  if (!response.ok) throw await buildApiError(response, 'Connection test failed')
  return (await response.json()) as EmailConnectionTestResult
}

/** Get email-specific settings. */
export async function getEmailSettings(): Promise<EmailSettingsInfo> {
  const response = await fetch(`${EMAIL_ENDPOINT}/settings/email`)
  if (!response.ok) throw await buildApiError(response, 'Get settings failed')
  return (await response.json()) as EmailSettingsInfo
}

/** Update email-specific settings. */
export async function updateEmailSettings(settings: EmailSettingsInfo): Promise<EmailSettingsInfo> {
  const response = await fetch(`${EMAIL_ENDPOINT}/settings/email`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })
  if (!response.ok) throw await buildApiError(response, 'Update settings failed')
  return (await response.json()) as EmailSettingsInfo
}

/** Clear the email cache (HTML + attachments). */
export async function clearEmailCache(): Promise<ClearCacheResult> {
  const response = await fetch(`${EMAIL_ENDPOINT}/cache`, {
    method: 'DELETE',
  })
  if (!response.ok) throw await buildApiError(response, 'Clear cache failed')
  return (await response.json()) as ClearCacheResult
}
