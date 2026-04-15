<script setup lang="ts">
/**
 * InboxWidget — email list / detail / compose workspace widget.
 *
 * Renders in the right-hand WorkspacePanel when the user selects "Inbox".
 * Three sub-views:
 *  1. Email list (with filter tabs and sync button)
 *  2. Email detail (with flag toggles and reply button)
 *  3. Compose form (new email or reply)
 */
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  RefreshCw,
  Mail,
  MailOpen,
  Star,
  StarOff,
  Paperclip,
  ArrowLeft,
  Reply,
  Send,
  PenSquare,
  Download,
  Loader2,
  MoreHorizontal,
  X,
  Inbox,
  SendHorizontal,
  Trash2,
  AlertCircle,
} from 'lucide-vue-next'
import { useEmailStore } from '@/stores/email'
import { getEmailHtmlUrl, getAttachmentUrl } from '@/api/email'
import ComposeEditor from '@/components/widgets/ComposeEditor.vue'

const { t } = useI18n()
const emailStore = useEmailStore()

// Compose form state
const composeTo = ref('')
const composeCc = ref('')
const composeSubject = ref('')
const composeBody = ref('')
const composeHtmlBody = ref('')

// Detail view flag context menu
const showFlagMenu = ref(false)

// Credentials error modal (spec: show as popup dialog, not inline banner)
const showCredentialsModal = ref(false)

onMounted(async () => {
  await emailStore.fetchEmails()
  // Apply auto_sync setting: trigger an IMAP sync in the background so
  // the user can already interact with cached emails while new ones arrive.
  try {
    const settings = await emailStore.fetchSettings()
    if (settings?.auto_sync) {
      emailStore.sync().catch(() => {
        // Non-fatal: auto-sync failure is silently ignored on mount
      })
    }
  } catch {
    // Settings fetch failure is non-fatal
  }
})

function formatDate(iso: string): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

async function handleSync(): Promise<void> {
  showCredentialsModal.value = false
  try {
    await emailStore.sync()
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : String(e)
    if (message.includes('EMAIL_CREDENTIALS_MISSING')) {
      showCredentialsModal.value = true
    }
  }
}

async function handleSelectEmail(uid: number): Promise<void> {
  await emailStore.selectEmail(uid)
  // Auto-mark as read
  if (emailStore.selectedEmail && !emailStore.selectedEmail.is_seen) {
    await emailStore.toggleFlag(uid, 'seen', true)
  }
}

async function handleToggleStar(uid: number, current: boolean): Promise<void> {
  const flagging = !current
  emailStore.showToast(flagging ? t('email.starPending') : t('email.unstarPending'), 'info', 2000)
  try {
    await emailStore.toggleFlag(uid, 'flagged', flagging)
    emailStore.showToast(flagging ? t('email.starSuccess') : t('email.unstarSuccess'), 'success')
  } catch {
    emailStore.showToast(flagging ? t('email.starFailed') : t('email.unstarFailed'), 'error')
  }
}

async function handleFlagAction(action: 'seen' | 'deleted' | 'spam'): Promise<void> {
  showFlagMenu.value = false
  if (!emailStore.selectedEmail) return
  const uid = emailStore.selectedEmail.uid
  emailStore.showToast(t('email.flagActionPending'), 'info', 2000)
  try {
    await emailStore.toggleFlag(uid, action, true)
    emailStore.showToast(t('email.flagActionSuccess'), 'success')
    if (action === 'deleted' || action === 'spam') {
      emailStore.clearSelection()
    }
  } catch {
    emailStore.showToast(t('email.flagActionFailed'), 'error')
  }
}

async function handleDownloadAttachment(uid: number, attId: number): Promise<void> {
  emailStore.showToast(t('email.downloadingAttachment'), 'info', 60000)
  try {
    await emailStore.downloadAttachment(uid, attId)
    emailStore.showToast(t('email.downloadSuccess'), 'success')
  } catch {
    emailStore.showToast(t('email.downloadFailed'), 'error')
  }
}

function handleReply(): void {
  if (!emailStore.selectedEmail) return
  const email = emailStore.selectedEmail
  composeTo.value = email.sender
  composeCc.value = ''
  composeSubject.value = email.subject.startsWith('Re:') ? email.subject : `Re: ${email.subject}`
  composeBody.value = `\n\n--- Original Message ---\nFrom: ${email.sender_name || email.sender}\nDate: ${email.date}\n\n${email.body_text}`
  emailStore.openReply(email)
}

function handleNewEmail(): void {
  composeTo.value = ''
  composeCc.value = ''
  composeSubject.value = ''
  composeBody.value = ''
  emailStore.openCompose()
}

async function handleSend(): Promise<void> {
  showCredentialsModal.value = false
  try {
    await emailStore.send({
      to: composeTo.value,
      cc: composeCc.value || undefined,
      subject: composeSubject.value,
      html_body: composeHtmlBody.value || undefined,
      plain_body: composeBody.value || undefined,
      in_reply_to: emailStore.replyTo?.message_id || undefined,
    })
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : String(e)
    if (message.includes('EMAIL_CREDENTIALS_MISSING')) {
      showCredentialsModal.value = true
    }
  }
}
</script>

<template>
  <div class="relative flex flex-col h-full">
    <!-- Email-open loading overlay -->
    <div
      v-if="emailStore.selectingEmail"
      class="absolute inset-0 z-40 flex flex-col items-center justify-center bg-white/80 backdrop-blur-sm"
    >
      <Loader2 class="w-8 h-8 text-blue-500 animate-spin mb-3" />
      <p class="text-sm text-gray-600">{{ t('email.loading') }}</p>
      <button
        class="mt-4 px-3 py-1 text-xs text-gray-500 border border-gray-300 rounded-lg hover:bg-gray-100"
        @click="emailStore.cancelSelectEmail()"
      >
        {{ t('email.loadingCancel') }}
      </button>
    </div>

    <!-- Toast notifications -->
    <div class="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      <div
        v-for="toast in emailStore.toasts"
        :key="toast.id"
        class="pointer-events-auto px-4 py-2 rounded-lg text-sm shadow-lg transition-all"
        :class="{
          'bg-white border border-gray-200 text-gray-700': toast.type === 'info',
          'bg-green-50 border border-green-200 text-green-700': toast.type === 'success',
          'bg-red-50 border border-red-200 text-red-700': toast.type === 'error',
        }"
      >
        {{ toast.message }}
      </div>
    </div>

    <!-- Credentials error modal -->
    <div
      v-if="showCredentialsModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
      @click.self="showCredentialsModal = false"
    >
      <div class="mx-4 w-full max-w-sm rounded-lg bg-white shadow-xl">
        <div class="flex items-center justify-between border-b border-gray-200 px-4 py-3">
          <h3 class="text-sm font-semibold text-gray-700">
            {{ t('email.credentialsRequiredTitle') }}
          </h3>
          <button class="text-gray-400 hover:text-gray-600" @click="showCredentialsModal = false">
            ✕
          </button>
        </div>
        <div class="px-4 py-4">
          <p class="text-sm text-gray-600">{{ t('email.credentialsRequired') }}</p>
        </div>
        <div class="flex justify-end border-t border-gray-200 px-4 py-3">
          <button
            class="px-4 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
            @click="showCredentialsModal = false"
          >
            {{ t('email.credentialsRequiredDismiss') }}
          </button>
        </div>
      </div>
    </div>

    <!-- ===== COMPOSE VIEW ===== -->
    <div v-if="emailStore.composeOpen" class="flex flex-col h-full">
      <!-- Compose header -->
      <div class="flex items-center gap-2 px-4 py-3 border-b border-gray-200 bg-white">
        <button
          class="p-1.5 rounded hover:bg-gray-100 text-gray-500"
          @click="emailStore.closeCompose()"
        >
          <ArrowLeft class="w-4 h-4" />
        </button>
        <span class="text-sm font-semibold text-gray-800">
          {{ emailStore.replyTo ? t('email.reply') : t('email.compose') }}
        </span>
      </div>

      <!-- Compose form -->
      <div class="flex-1 overflow-y-auto p-4 space-y-3">
        <div>
          <label class="block text-xs font-medium text-gray-600 mb-1">{{ t('email.to') }}</label>
          <input
            v-model="composeTo"
            type="text"
            class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            :placeholder="t('email.toPlaceholder')"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-600 mb-1">{{ t('email.cc') }}</label>
          <input
            v-model="composeCc"
            type="text"
            class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            :placeholder="t('email.ccPlaceholder')"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-600 mb-1">{{
            t('email.subject')
          }}</label>
          <input
            v-model="composeSubject"
            type="text"
            class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-600 mb-1">{{ t('email.body') }}</label>
          <ComposeEditor v-model="composeHtmlBody" :placeholder="t('compose.editorPlaceholder')" />
        </div>
      </div>

      <!-- Send button -->
      <div class="px-4 py-3 border-t border-gray-200 bg-white">
        <button
          class="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="emailStore.sending || !composeTo.trim()"
          @click="handleSend"
        >
          <Loader2 v-if="emailStore.sending" class="w-4 h-4 animate-spin" />
          <Send v-else class="w-4 h-4" />
          {{ emailStore.sending ? t('email.sending') : t('email.send') }}
        </button>
      </div>
    </div>

    <!-- ===== DETAIL VIEW ===== -->
    <div v-else-if="emailStore.selectedEmail" class="flex flex-col h-full">
      <!-- Detail header -->
      <div class="flex items-center gap-2 px-4 py-3 border-b border-gray-200 bg-white">
        <button
          class="p-1.5 rounded hover:bg-gray-100 text-gray-500"
          @click="emailStore.clearSelection()"
        >
          <ArrowLeft class="w-4 h-4" />
        </button>
        <span class="flex-1 text-sm font-semibold text-gray-800 truncate">
          {{ emailStore.selectedEmail.subject || t('email.noSubject') }}
        </span>
        <button
          class="p-1.5 rounded hover:bg-gray-100 text-gray-500"
          :title="t('email.reply')"
          @click="handleReply"
        >
          <Reply class="w-4 h-4" />
        </button>
        <button
          class="p-1.5 rounded hover:bg-gray-100"
          :class="emailStore.selectedEmail.is_flagged ? 'text-yellow-500' : 'text-gray-400'"
          @click="
            handleToggleStar(emailStore.selectedEmail.uid, emailStore.selectedEmail.is_flagged)
          "
        >
          <Star v-if="emailStore.selectedEmail.is_flagged" class="w-4 h-4 fill-current" />
          <StarOff v-else class="w-4 h-4" />
        </button>
        <!-- Flag actions menu -->
        <div class="relative">
          <button
            class="p-1.5 rounded hover:bg-gray-100 text-gray-500"
            @click="showFlagMenu = !showFlagMenu"
          >
            <MoreHorizontal class="w-4 h-4" />
          </button>
          <div
            v-if="showFlagMenu"
            class="absolute right-0 top-full mt-1 w-44 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-30"
          >
            <button
              class="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
              @click="handleFlagAction('seen')"
            >
              {{ t('email.markUnread') }}
            </button>
            <button
              class="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
              @click="handleFlagAction('deleted')"
            >
              {{ t('email.moveToTrash') }}
            </button>
            <button
              class="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50"
              @click="handleFlagAction('spam')"
            >
              {{ t('email.markSpam') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Detail body -->
      <div class="flex-1 overflow-y-auto p-4 space-y-4">
        <!-- Sender / recipients -->
        <div class="space-y-1">
          <div class="text-sm">
            <span class="font-medium text-gray-800">
              {{ emailStore.selectedEmail.sender_name || emailStore.selectedEmail.sender }}
            </span>
            <span class="text-gray-500 ml-1">&lt;{{ emailStore.selectedEmail.sender }}&gt;</span>
          </div>
          <div class="text-xs text-gray-500">
            {{ t('email.to') }}: {{ emailStore.selectedEmail.recipients }}
          </div>
          <div v-if="emailStore.selectedEmail.cc" class="text-xs text-gray-500">
            {{ t('email.cc') }}: {{ emailStore.selectedEmail.cc }}
          </div>
          <div class="text-xs text-gray-400">
            {{ formatDate(emailStore.selectedEmail.date) }}
          </div>
        </div>

        <!-- HTML body (iframe) or text fallback -->
        <div class="border border-gray-200 rounded-lg bg-white overflow-hidden">
          <iframe
            v-if="emailStore.selectedEmail.html_local_path"
            :src="getEmailHtmlUrl(emailStore.selectedEmail.uid)"
            class="w-full min-h-[400px] border-0"
            sandbox="allow-same-origin"
          />
          <pre v-else class="p-4 text-sm text-gray-700 whitespace-pre-wrap font-sans">{{
            emailStore.selectedEmail.body_text
          }}</pre>
        </div>

        <!-- Attachments -->
        <div v-if="emailStore.selectedEmail.attachments.length > 0" class="space-y-2">
          <h4 class="text-xs font-semibold text-gray-600 uppercase">
            {{ t('email.attachments') }} ({{ emailStore.selectedEmail.attachments.length }})
          </h4>
          <div class="space-y-1">
            <div
              v-for="att in emailStore.selectedEmail.attachments"
              :key="att.id"
              class="flex items-center gap-2 px-3 py-2 text-sm bg-gray-50 rounded-lg"
            >
              <Paperclip class="w-4 h-4 text-gray-400 flex-shrink-0" />
              <span class="flex-1 truncate text-gray-700">{{ att.filename }}</span>
              <span class="text-xs text-gray-400">{{ formatFileSize(att.file_size) }}</span>
              <!-- Inline image already downloaded: show link -->
              <a
                v-if="att.content_id || att.is_downloaded"
                :href="getAttachmentUrl(emailStore.selectedEmail.uid, att.id)"
                target="_blank"
                class="p-1 rounded hover:bg-gray-200 text-gray-400"
                :title="t('email.downloadAttachment')"
              >
                <Download class="w-4 h-4" />
              </a>
              <!-- Regular attachment: on-demand download -->
              <template v-else>
                <Loader2
                  v-if="emailStore.downloadingAtts.has(att.id)"
                  class="w-4 h-4 text-blue-500 animate-spin"
                />
                <button
                  v-else
                  class="px-2 py-0.5 text-xs rounded bg-blue-100 text-blue-700 hover:bg-blue-200"
                  @click="handleDownloadAttachment(emailStore.selectedEmail.uid, att.id)"
                >
                  {{ t('email.downloadAttachment') }}
                </button>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== LIST VIEW ===== -->
    <div v-else class="flex h-full">
      <!-- Folder sidebar -->
      <div
        class="w-28 flex-shrink-0 border-r border-gray-200 bg-gray-50 flex flex-col py-2 gap-0.5"
      >
        <button
          v-for="folder in [
            { key: 'INBOX', label: t('email.folderInbox'), icon: 'inbox' },
            { key: 'Sent Messages', label: t('email.folderSent'), icon: 'send' },
            { key: '__STARRED__', label: t('email.folderStarred'), icon: 'star' },
            { key: 'Deleted Messages', label: t('email.folderTrash'), icon: 'trash' },
            { key: 'Junk', label: t('email.folderSpam'), icon: 'alert' },
          ]"
          :key="folder.key"
          class="flex flex-col items-center gap-0.5 px-2 py-2 mx-1 rounded-lg text-xs transition-colors"
          :class="
            emailStore.currentFolder === folder.key
              ? 'bg-blue-100 text-blue-700 font-medium'
              : 'text-gray-500 hover:bg-gray-100'
          "
          @click="emailStore.setFolder(folder.key)"
        >
          <Inbox v-if="folder.icon === 'inbox'" class="w-4 h-4" />
          <SendHorizontal v-else-if="folder.icon === 'send'" class="w-4 h-4" />
          <Star v-else-if="folder.icon === 'star'" class="w-4 h-4" />
          <Trash2 v-else-if="folder.icon === 'trash'" class="w-4 h-4" />
          <AlertCircle v-else class="w-4 h-4" />
          <span class="text-center leading-tight" style="font-size: 10px">{{ folder.label }}</span>
        </button>
      </div>

      <!-- Main list area -->
      <div class="flex-1 flex flex-col min-w-0">
        <!-- List header -->
        <div class="flex items-center gap-2 px-4 py-3 border-b border-gray-200 bg-white">
          <!-- Filter tabs -->
          <div class="flex gap-1 flex-1">
            <button
              v-for="f in ['all', 'unread', 'flagged'] as const"
              :key="f"
              class="px-3 py-1 text-xs font-medium rounded-full transition-colors"
              :class="
                emailStore.filter === f
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-gray-500 hover:bg-gray-100'
              "
              @click="emailStore.setFilter(f)"
            >
              {{
                f === 'all'
                  ? t('email.filterAll')
                  : f === 'unread'
                    ? t('email.filterUnread')
                    : t('email.filterFlagged')
              }}
            </button>
          </div>

          <!-- Actions -->
          <button
            class="p-1.5 rounded hover:bg-gray-100 text-gray-500"
            :title="t('email.compose')"
            @click="handleNewEmail"
          >
            <PenSquare class="w-4 h-4" />
          </button>
          <button
            class="p-1.5 rounded hover:bg-gray-100 text-gray-500"
            :disabled="emailStore.syncing"
            :title="t('email.sync')"
            @click="handleSync"
          >
            <Loader2 v-if="emailStore.syncing" class="w-4 h-4 animate-spin" />
            <RefreshCw v-else class="w-4 h-4" />
          </button>
        </div>

        <!-- Email list -->
        <div class="flex-1 overflow-y-auto">
          <!-- Loading state -->
          <div
            v-if="emailStore.loading && emailStore.emails.length === 0"
            class="flex items-center justify-center h-32"
          >
            <Loader2 class="w-5 h-5 text-gray-400 animate-spin" />
          </div>

          <!-- Empty state -->
          <div
            v-else-if="emailStore.emails.length === 0"
            class="flex flex-col items-center justify-center h-32 text-gray-400"
          >
            <Mail class="w-8 h-8 mb-2" />
            <p class="text-sm">{{ t('email.empty') }}</p>
            <button class="mt-2 text-xs text-blue-600 hover:underline" @click="handleSync">
              {{ t('email.syncNow') }}
            </button>
          </div>

          <!-- Email items -->
          <button
            v-for="email in emailStore.emails"
            :key="email.uid"
            class="w-full text-left px-4 py-3 border-b border-gray-100 hover:bg-blue-50/50 transition-colors"
            :class="{ 'bg-white': email.is_seen, 'bg-blue-50/30': !email.is_seen }"
            @click="handleSelectEmail(email.uid)"
          >
            <div class="flex items-start gap-2">
              <!-- Unread indicator -->
              <div class="flex-shrink-0 mt-1.5">
                <MailOpen v-if="email.is_seen" class="w-4 h-4 text-gray-300" />
                <Mail v-else class="w-4 h-4 text-blue-500" />
              </div>

              <!-- Content -->
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span
                    class="text-sm truncate"
                    :class="email.is_seen ? 'text-gray-600' : 'font-semibold text-gray-800'"
                  >
                    {{ email.sender_name || email.sender }}
                  </span>
                  <span class="flex-shrink-0 text-xs text-gray-400">
                    {{ formatDate(email.date) }}
                  </span>
                </div>
                <div
                  class="text-sm truncate"
                  :class="email.is_seen ? 'text-gray-500' : 'font-medium text-gray-700'"
                >
                  {{ email.subject || t('email.noSubject') }}
                </div>
                <div class="text-xs text-gray-400 truncate mt-0.5">
                  {{ email.preview }}
                </div>
              </div>

              <!-- Indicators -->
              <div class="flex flex-col items-center gap-1 flex-shrink-0">
                <button
                  class="p-0.5"
                  :class="
                    email.is_flagged ? 'text-yellow-500' : 'text-gray-300 hover:text-yellow-400'
                  "
                  @click.stop="handleToggleStar(email.uid, email.is_flagged)"
                >
                  <Star v-if="email.is_flagged" class="w-3.5 h-3.5 fill-current" />
                  <Star v-else class="w-3.5 h-3.5" />
                </button>
                <Paperclip v-if="email.has_attachments" class="w-3.5 h-3.5 text-gray-400" />
              </div>
            </div>
          </button>
        </div>

        <!-- Error bar -->
        <div
          v-if="emailStore.error"
          class="px-4 py-2 bg-red-50 text-red-600 text-xs border-t border-red-100"
        >
          {{ emailStore.error }}
        </div>
      </div>
      <!-- end main list area -->
    </div>
  </div>
</template>
