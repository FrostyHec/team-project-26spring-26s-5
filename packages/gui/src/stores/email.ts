/**
 * Pinia store for the email feature.
 *
 * Manages email list, detail view, sync state, and compose mode.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  syncEmails,
  listEmails,
  getEmailDetail,
  updateEmailFlag,
  sendEmail,
  downloadAttachment as apiDownloadAttachment,
  getEmailSettings,
  updateEmailSettings as apiUpdateEmailSettings,
  testEmailConnection,
  clearEmailCache,
  type AttachmentInfo,
  type EmailSummary,
  type EmailDetail,
  type EmailSyncResult,
  type SendEmailRequest,
  type EmailSettingsInfo,
  type EmailConnectionTestResult,
  type ClearCacheResult,
} from '@/api/email'

export const useEmailStore = defineStore('email', () => {
  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------

  const emails = ref<EmailSummary[]>([])
  const selectedEmail = ref<EmailDetail | null>(null)
  const loading = ref(false)
  const syncing = ref(false)
  const sending = ref(false)
  const error = ref<string | null>(null)
  const totalCount = ref(0)
  const lastSyncAt = ref<string | null>(null)

  /** Whether the compose panel is open. */
  const composeOpen = ref(false)
  /** Pre-filled reply data for the compose panel. */
  const replyTo = ref<EmailDetail | null>(null)

  /** Active filter: 'all' | 'unread' | 'flagged'. */
  const filter = ref<'all' | 'unread' | 'flagged'>('all')

  /** Current mailbox folder (INBOX / Sent Messages / etc.). */
  const currentFolder = ref<string>('INBOX')

  /** True while an email detail is being fetched (open-email loading overlay). */
  const selectingEmail = ref(false)

  /** AbortController used to cancel an in-progress selectEmail fetch.
   * Note: signal is not currently threaded through getEmailDetail, so
   * cancelSelectEmail acts as a UI-state reset only. */
  let _selectInProgress = false

  /** Set of attachment IDs currently being downloaded. */
  const downloadingAtts = ref<Set<number>>(new Set())

  /** Toast notifications queue: {id, message, type}[] */
  const toasts = ref<{ id: number; message: string; type: 'info' | 'success' | 'error' }[]>([])
  let _toastSeq = 0

  /**
   * Per-folder email list cache.  Used to restore a previously fetched list
   * instantly when the user switches back to a folder they have already visited,
   * so the list is never blank while a background refresh runs.
   */
  const folderCache = new Map<string, EmailSummary[]>()

  // ---------------------------------------------------------------------------
  // Computed
  // ---------------------------------------------------------------------------

  const unreadCount = computed(() => emails.value.filter((e) => !e.is_seen).length)

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------

  /** Sync emails from the mail server. */
  async function sync(days?: number): Promise<EmailSyncResult> {
    // __STARRED__ is a virtual pseudo-folder; sync the inbox instead.
    const folderToSync = currentFolder.value === '__STARRED__' ? 'INBOX' : currentFolder.value
    syncing.value = true
    error.value = null
    try {
      const result = await syncEmails(days, folderToSync)
      lastSyncAt.value = result.synced_at
      totalCount.value = result.total_count
      // Refresh list after sync
      await fetchEmails()
      return result
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
      throw e
    } finally {
      syncing.value = false
    }
  }

  /** Fetch email list from the local store. */
  async function fetchEmails(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const opts: { flagged_only?: boolean; unseen_only?: boolean; folder?: string } = {}
      if (currentFolder.value === '__STARRED__') {
        // Virtual pseudo-folder: show flagged emails across all real mailboxes.
        opts.flagged_only = true
      } else {
        // Always pass the folder so that INBOX does not bleed Sent/Trash emails.
        opts.folder = currentFolder.value
        if (filter.value === 'flagged') opts.flagged_only = true
        if (filter.value === 'unread') opts.unseen_only = true
      }
      emails.value = await listEmails(opts)
      // Save to per-folder cache so switching back to this folder is instant.
      folderCache.set(currentFolder.value, [...emails.value])
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  /** Select and load email detail (shows full-panel loading overlay). */
  async function selectEmail(uid: number): Promise<void> {
    _selectInProgress = true
    selectingEmail.value = true
    error.value = null
    try {
      selectedEmail.value = await getEmailDetail(uid, currentFolder.value)
      // The backend marks the email as \Seen on the IMAP server when fetching
      // its content (RFC822).  Reflect that optimistically in the list so the
      // unread indicator disappears without needing a full re-fetch.
      if (selectedEmail.value?.is_seen) {
        const inList = emails.value.find((e) => e.uid === uid)
        if (inList) inList.is_seen = true
      }
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      selectingEmail.value = false
      _selectInProgress = false
    }
  }

  /** Cancel the in-progress email open fetch (resets UI state only). */
  function cancelSelectEmail(): void {
    _selectInProgress = false
    selectingEmail.value = false
  }

  /** Clear selected email (back to list). */
  function clearSelection(): void {
    selectedEmail.value = null
  }

  /** Toggle a flag on an email. */
  async function toggleFlag(
    uid: number,
    flag: 'seen' | 'flagged' | 'answered' | 'deleted' | 'spam',
    value: boolean,
  ): Promise<void> {
    await updateEmailFlag(uid, flag, value, currentFolder.value)
    // Update local state
    const email = emails.value.find((e) => e.uid === uid)
    if (email) {
      if (flag === 'seen') email.is_seen = value
      if (flag === 'flagged') email.is_flagged = value
      if (flag === 'answered') email.is_answered = value
    }
    if (selectedEmail.value?.uid === uid) {
      if (flag === 'seen') selectedEmail.value.is_seen = value
      if (flag === 'flagged') selectedEmail.value.is_flagged = value
      if (flag === 'answered') selectedEmail.value.is_answered = value
    }
  }

  /** Send an email. */
  async function send(request: SendEmailRequest): Promise<void> {
    sending.value = true
    error.value = null
    try {
      await sendEmail(request)
      composeOpen.value = false
      replyTo.value = null
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
      throw e
    } finally {
      sending.value = false
    }
  }

  /** Open compose panel for a new email. */
  function openCompose(): void {
    replyTo.value = null
    composeOpen.value = true
  }

  /** Open compose panel for a reply. */
  function openReply(email: EmailDetail): void {
    replyTo.value = email
    composeOpen.value = true
  }

  /** Close compose panel. */
  function closeCompose(): void {
    composeOpen.value = false
    replyTo.value = null
  }

  /** Switch to a different mailbox folder and refresh. */
  async function setFolder(folder: string): Promise<void> {
    currentFolder.value = folder
    filter.value = 'all'
    // Restore cached emails immediately so the list is never blank while the
    // background API call lands.  The loading spinner only shows if no cached
    // data exists for this folder yet.
    const cached = folderCache.get(folder)
    if (cached) emails.value = cached
    await fetchEmails()
  }

  // ------------------------------------------------------------------
  // Toast helpers
  // ------------------------------------------------------------------

  function showToast(
    message: string,
    type: 'info' | 'success' | 'error' = 'info',
    duration = 3000,
  ): void {
    const id = ++_toastSeq
    toasts.value.push({ id, message, type })
    setTimeout(() => {
      toasts.value = toasts.value.filter((t) => t.id !== id)
    }, duration)
  }

  // ------------------------------------------------------------------
  // Attachment download
  // ------------------------------------------------------------------

  async function downloadAttachment(uid: number, attId: number): Promise<AttachmentInfo> {
    downloadingAtts.value = new Set([...downloadingAtts.value, attId])
    try {
      const updated = await apiDownloadAttachment(uid, attId)
      // Update local attachment record in selectedEmail
      if (selectedEmail.value?.uid === uid) {
        const idx = selectedEmail.value.attachments.findIndex((a) => a.id === attId)
        if (idx >= 0) {
          selectedEmail.value.attachments[idx] = updated
        }
      }
      return updated
    } finally {
      const next = new Set(downloadingAtts.value)
      next.delete(attId)
      downloadingAtts.value = next
    }
  }

  /** Set the active filter and refresh. */
  async function setFilter(f: 'all' | 'unread' | 'flagged'): Promise<void> {
    filter.value = f
    await fetchEmails()
  }

  /** Test email connection. */
  async function testConnection(): Promise<EmailConnectionTestResult> {
    return await testEmailConnection()
  }

  /** Get email settings. */
  async function fetchSettings(): Promise<EmailSettingsInfo> {
    return await getEmailSettings()
  }

  /** Update email settings. */
  async function updateSettings(settings: EmailSettingsInfo): Promise<EmailSettingsInfo> {
    return await apiUpdateEmailSettings(settings)
  }

  /** Clear email cache. */
  async function clearCache(): Promise<ClearCacheResult> {
    return await clearEmailCache()
  }

  return {
    // State
    emails,
    selectedEmail,
    loading,
    syncing,
    sending,
    error,
    totalCount,
    lastSyncAt,
    composeOpen,
    replyTo,
    filter,
    currentFolder,
    selectingEmail,
    downloadingAtts,
    toasts,
    // Computed
    unreadCount,
    // Actions
    sync,
    fetchEmails,
    selectEmail,
    cancelSelectEmail,
    clearSelection,
    toggleFlag,
    send,
    openCompose,
    openReply,
    closeCompose,
    setFilter,
    setFolder,
    showToast,
    downloadAttachment,
    testConnection,
    fetchSettings,
    updateSettings,
    clearCache,
  }
})
