<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  AlertCircle,
  ArrowLeft,
  CalendarDays,
  ExternalLink,
  FileText,
  Loader2,
  Newspaper,
  RefreshCw,
  Search,
  Sparkles,
} from 'lucide-vue-next'
import {
  fetchCampusNews,
  fetchCampusNewsDetail,
  fetchNewsPushSettings,
  generateCampusNewsReport,
  saveNewsPushSettings,
  type CampusNewsArticle,
  type CampusNewsArticleDetail,
  type CampusNewsReport,
  type CampusNewsSourceType,
  type NewsPushSettings,
} from '@/api/agent'

type NewsSourceFilter = CampusNewsSourceType | 'all'

interface NewsHighlight {
  title?: string
  category?: string
  summary?: string
  source_type?: CampusNewsArticle['source_type']
  source_name?: string
}

interface NewsSource {
  title?: string
  source?: string
  url?: string
  source_type?: CampusNewsArticle['source_type']
  source_name?: string
}

const props = defineProps<{
  data?: Record<string, unknown>
}>()

const articles = ref<CampusNewsArticle[]>([])
const selectedDate = ref('')
const keyword = ref('')
const selectedSource = ref<NewsSourceFilter>('all')
const mode = ref<'daily' | 'search' | 'latest'>('daily')
const activeDate = ref('')
const activeQuery = ref('')
const loading = ref(false)
const errorMsg = ref('')
const selectedArticle = ref<CampusNewsArticleDetail | null>(null)
const detailLoading = ref(false)
const detailError = ref('')
const dailyReport = ref<CampusNewsReport | null>(null)
const selectedReport = ref<CampusNewsReport | null>(null)
const reportLoading = ref(false)
const reportError = ref('')

const pushSettings = ref<NewsPushSettings>({
  enabled: false,
  push_time: '08:30',
  limit: 20,
})
const pushLoading = ref(false)
const pushError = ref('')
const pushStatus = ref('')

const digestHighlights = computed<NewsHighlight[]>(() =>
  Array.isArray(props.data?.highlights) ? (props.data.highlights as NewsHighlight[]) : [],
)
const digestSources = computed<NewsSource[]>(() =>
  Array.isArray(props.data?.sources) ? (props.data.sources as NewsSource[]) : [],
)

const sourceOptions: Array<{ label: string; value: NewsSourceFilter }> = [
  { label: 'All sources', value: 'all' },
  { label: 'Email', value: 'email' },
  { label: 'Mock', value: 'mock' },
  { label: 'WeChat', value: 'wechat' },
  { label: 'Official site', value: 'official_site' },
  { label: 'RSS', value: 'rss' },
  { label: 'API', value: 'api' },
  { label: 'Manual', value: 'manual' },
]

const displayItems = computed<NewsHighlight[]>(() => {
  if (articles.value.length > 0) {
    return articles.value.map((article) => ({
      title: article.title,
      category: article.category,
      summary: article.summary,
      source_type: article.source_type,
      source_name: article.source_name || article.source,
    }))
  }
  return digestHighlights.value
})

const sourceItems = computed<NewsSource[]>(() => {
  if (articles.value.length > 0) {
    return articles.value.map((article) => ({
      title: article.title,
      source: article.source,
      url: article.url,
      source_type: article.source_type,
      source_name: article.source_name,
    }))
  }
  return digestSources.value
})

const emptyMessage = computed(() => {
  if (mode.value === 'search') {
    return activeQuery.value
      ? `No campus news found for "${activeQuery.value}".`
      : 'Enter a keyword to search campus news.'
  }
  return activeDate.value
    ? `No campus news found for ${activeDate.value}.`
    : 'No campus news found.'
})

function formatCategory(category?: string): string {
  if (!category) return 'Campus'
  return category
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function formatSourceType(sourceType?: CampusNewsArticle['source_type']): string {
  const sourceTypeLabels: Record<NonNullable<CampusNewsArticle['source_type']>, string> = {
    mock: 'Mock',
    email: 'Email',
    wechat: 'WeChat',
    official_site: 'Official Site',
    rss: 'RSS',
    api: 'API',
    manual: 'Manual',
    unknown: 'Unknown',
  }
  return sourceTypeLabels[sourceType ?? 'unknown']
}

function formatSourceFilter(source: NewsSourceFilter): string {
  return source === 'all' ? 'All sources' : formatSourceType(source)
}

function formatSourceLabel(item: NewsHighlight | NewsSource | CampusNewsArticle): string {
  const sourceType = formatSourceType(item.source_type)
  const sourceName =
    'source_name' in item && item.source_name
      ? item.source_name
      : 'source' in item && item.source
        ? item.source
        : ''
  return sourceName ? `${sourceType} · ${sourceName}` : sourceType
}

function isSafeExternalUrl(url?: string): boolean {
  if (!url) return false
  try {
    const parsedUrl = new URL(url)
    return parsedUrl.protocol === 'http:' || parsedUrl.protocol === 'https:'
  } catch {
    return false
  }
}

async function loadNews(): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  selectedArticle.value = null
  selectedReport.value = null
  detailError.value = ''
  const query = keyword.value.trim()
  try {
    const response = await fetchCampusNews({
      targetDate: selectedDate.value || undefined,
      query: query || undefined,
      source: selectedSource.value,
      limit: 20,
    })
    articles.value = response.articles
    mode.value = response.mode
    activeDate.value = response.date || ''
    activeQuery.value = response.query || ''
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : 'Failed to load campus news'
  } finally {
    loading.value = false
  }
}

async function searchByKeyword(): Promise<void> {
  await loadNews()
}

function handleRefresh(): void {
  selectedArticle.value = null
  selectedReport.value = null
  detailError.value = ''
  void loadNews()
}

function clearDateFilter(): void {
  selectedDate.value = ''
  void loadNews()
}

async function openArticle(article: CampusNewsArticle): Promise<void> {
  detailLoading.value = true
  detailError.value = ''
  selectedReport.value = null
  try {
    selectedArticle.value = await fetchCampusNewsDetail(article.id)
  } catch (e) {
    detailError.value = e instanceof Error ? e.message : 'Failed to load news detail'
  } finally {
    detailLoading.value = false
  }
}

async function openArticleById(newsId: string): Promise<void> {
  detailLoading.value = true
  detailError.value = ''
  selectedReport.value = null
  try {
    selectedArticle.value = await fetchCampusNewsDetail(newsId)
  } catch (e) {
    detailError.value = e instanceof Error ? e.message : 'Failed to load news detail'
  } finally {
    detailLoading.value = false
  }
}

async function generateDailyReport(): Promise<void> {
  reportLoading.value = true
  reportError.value = ''
  selectedArticle.value = null
  selectedReport.value = null
  try {
    const report = await generateCampusNewsReport({
      targetDate: selectedDate.value || undefined,
      query: keyword.value.trim() || undefined,
      source: selectedSource.value,
      limit: 20,
    })
    dailyReport.value = report
    selectedReport.value = report
  } catch (e) {
    reportError.value = e instanceof Error ? e.message : 'Failed to generate daily report'
  } finally {
    reportLoading.value = false
  }
}

function closeDetail(): void {
  selectedArticle.value = null
  selectedReport.value = null
  detailError.value = ''
}

async function loadPushSettings(): Promise<void> {
  pushError.value = ''
  try {
    pushSettings.value = await fetchNewsPushSettings()
  } catch (e) {
    pushError.value = e instanceof Error ? e.message : 'Failed to load push settings'
  }
}

async function savePushConfig(): Promise<void> {
  pushLoading.value = true
  pushError.value = ''
  pushStatus.value = ''
  try {
    pushSettings.value = await saveNewsPushSettings(pushSettings.value)
    pushStatus.value = 'Daily push settings saved.'
  } catch (e) {
    pushError.value = e instanceof Error ? e.message : 'Failed to save push settings'
  } finally {
    pushLoading.value = false
  }
}

onMounted(() => {
  void loadNews()
  void loadPushSettings()
})
</script>

<template>
  <div class="flex min-h-full flex-col bg-gray-50 text-gray-800">
    <div class="border-b border-gray-200 bg-white px-4 py-4">
      <div>
        <div class="mb-2 flex items-center gap-2">
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-100">
            <Newspaper class="h-4 w-4 text-amber-600" />
          </div>
          <div>
            <h3 class="text-base font-semibold leading-tight text-gray-900">Daily Campus Digest</h3>
            <p class="text-xs text-gray-500">
              Mock campus announcements, events, and opportunities
            </p>
          </div>
        </div>

        <div class="mt-4 grid gap-2">
          <label
            class="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 focus-within:border-blue-300 focus-within:bg-white"
          >
            <CalendarDays class="h-4 w-4 flex-shrink-0 text-gray-400" />
            <input
              v-model="selectedDate"
              type="date"
              class="min-w-0 flex-1 bg-transparent text-sm text-gray-700 outline-none"
              @change="loadNews"
            />
            <button
              v-if="selectedDate"
              type="button"
              class="rounded px-1.5 py-0.5 text-xs text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
              @click="clearDateFilter"
            >
              Clear
            </button>
          </label>

          <form
            class="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 focus-within:border-blue-300 focus-within:bg-white"
            @submit.prevent="searchByKeyword"
          >
            <Search class="h-4 w-4 flex-shrink-0 text-gray-400" />
            <input
              v-model="keyword"
              type="search"
              placeholder="Search by keyword, e.g. career"
              class="min-w-0 flex-1 bg-transparent text-sm text-gray-700 placeholder:text-gray-400 focus:outline-none"
            />
            <button
              class="rounded-md bg-blue-600 px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-blue-700"
              type="submit"
            >
              Search
            </button>
          </form>

          <label
            class="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 focus-within:border-blue-300 focus-within:bg-white"
          >
            <span class="text-xs font-medium text-gray-500">Source</span>
            <select
              v-model="selectedSource"
              class="min-w-0 flex-1 bg-transparent text-sm text-gray-700 outline-none"
              @change="loadNews"
            >
              <option v-for="option in sourceOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>

          <div class="rounded-lg border border-gray-200 bg-gray-50 px-3 py-3">
            <div class="flex items-center justify-between gap-3">
              <label class="flex items-center gap-2 text-sm font-medium text-gray-700">
                <input v-model="pushSettings.enabled" type="checkbox" class="h-4 w-4" />
                Daily email push
              </label>
              <input
                v-model="pushSettings.push_time"
                type="time"
                class="rounded-md border border-gray-200 bg-white px-2 py-1 text-sm text-gray-700"
              />
            </div>

            <div class="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                class="rounded-md bg-gray-700 px-3 py-1.5 text-xs font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="pushLoading"
                @click="savePushConfig"
              >
                Save Push
              </button>
            </div>

            <p v-if="pushStatus" class="mt-2 text-xs text-green-600">{{ pushStatus }}</p>
            <p v-if="pushError" class="mt-2 text-xs text-red-600">{{ pushError }}</p>
          </div>
        </div>

        <div class="mt-4 flex flex-wrap items-center gap-2">
          <span class="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600">
            {{ activeDate || 'All dates' }}
          </span>
          <span class="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600">
            {{ formatSourceFilter(selectedSource) }}
          </span>
          <span v-if="activeQuery" class="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600">
            Keyword: {{ activeQuery }}
          </span>
          <span class="rounded-full bg-amber-100 px-3 py-1 text-xs text-amber-700">
            {{
              mode === 'search' ? 'Search results' : mode === 'latest' ? 'All news' : 'Daily news'
            }}
          </span>
          <span class="rounded-full bg-blue-100 px-3 py-1 text-xs text-blue-700">
            {{ displayItems.length }} headlines
          </span>
          <button
            class="ml-auto flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            title="Generate daily report"
            :disabled="loading || reportLoading"
            @click="generateDailyReport"
          >
            <Loader2 v-if="reportLoading" class="h-3.5 w-3.5 animate-spin" />
            <FileText v-else class="h-3.5 w-3.5" />
            Generate Daily
          </button>
          <button
            class="rounded-md p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 disabled:opacity-50"
            title="Refresh news"
            :disabled="loading"
            @click="handleRefresh"
          >
            <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
            <RefreshCw v-else class="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>

    <div v-if="reportError" class="m-4 rounded-lg border border-red-200 bg-red-50 p-3">
      <div class="flex items-start gap-2 text-sm text-red-600">
        <AlertCircle class="mt-0.5 h-4 w-4 flex-shrink-0" />
        <span>{{ reportError }}</span>
      </div>
    </div>

    <div v-if="errorMsg" class="m-4 rounded-lg border border-red-200 bg-red-50 p-3">
      <div class="flex items-start gap-2 text-sm text-red-600">
        <AlertCircle class="mt-0.5 h-4 w-4 flex-shrink-0" />
        <span>{{ errorMsg }}</span>
      </div>
    </div>

    <div
      v-if="selectedArticle || selectedReport || detailLoading || detailError"
      class="flex-1 overflow-y-auto bg-gray-50"
    >
      <div class="border-b border-gray-200 bg-white px-4 py-3">
        <button
          class="flex items-center gap-2 rounded-md px-2 py-1 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-100 hover:text-gray-900"
          @click="closeDetail"
        >
          <ArrowLeft class="h-4 w-4" />
          Back to news
        </button>
      </div>

      <div v-if="detailLoading" class="flex items-center justify-center p-10">
        <div class="flex items-center gap-2 text-sm text-gray-400">
          <Loader2 class="h-4 w-4 animate-spin" />
          Loading news detail...
        </div>
      </div>

      <div v-else-if="detailError" class="m-4 rounded-lg border border-red-200 bg-red-50 p-3">
        <div class="flex items-start gap-2 text-sm text-red-600">
          <AlertCircle class="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>{{ detailError }}</span>
        </div>
      </div>

      <article v-else-if="selectedReport" class="space-y-4 p-4">
        <div class="rounded-xl border border-blue-100 bg-white p-5 shadow-sm">
          <div class="mb-4 flex flex-wrap items-center gap-2">
            <span class="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
              Daily Report
            </span>
            <span class="rounded-full bg-gray-100 px-2.5 py-1 text-xs text-gray-500">
              {{ selectedReport.filter_text }}
            </span>
          </div>

          <h4 class="text-lg font-semibold leading-7 text-gray-900">
            {{ selectedReport.title }}
          </h4>
          <p class="mt-2 text-xs text-gray-400">Generated at {{ selectedReport.generated_at }}</p>
          <p class="mt-4 text-sm leading-6 text-gray-600">
            {{ selectedReport.summary }}
          </p>
        </div>

        <section class="rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
          <h5 class="text-sm font-semibold uppercase tracking-[0.12em] text-gray-400">
            Key Points
          </h5>
          <ul class="mt-3 space-y-3">
            <li
              v-for="(point, index) in selectedReport.key_points"
              :key="`point-${index}`"
              class="rounded-lg bg-gray-50 px-3 py-3 text-sm leading-6 text-gray-700"
            >
              {{ point }}
            </li>
          </ul>
          <p v-if="selectedReport.key_points.length === 0" class="mt-3 text-sm text-gray-400">
            No key points generated.
          </p>
        </section>

        <section class="rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
          <h5 class="text-sm font-semibold uppercase tracking-[0.12em] text-gray-400">
            Action Items
          </h5>
          <ul class="mt-3 space-y-3">
            <li
              v-for="(item, index) in selectedReport.action_items"
              :key="`action-${index}`"
              class="rounded-lg bg-amber-50 px-3 py-3 text-sm leading-6 text-amber-800"
            >
              {{ item }}
            </li>
          </ul>
          <p v-if="selectedReport.action_items.length === 0" class="mt-3 text-sm text-gray-400">
            No action items found.
          </p>
        </section>

        <section class="rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
          <h5 class="text-sm font-semibold uppercase tracking-[0.12em] text-gray-400">
            Referenced News
          </h5>
          <div class="mt-3 space-y-2">
            <button
              v-for="article in selectedReport.articles"
              :key="article.id"
              type="button"
              class="block w-full rounded-lg bg-gray-50 px-3 py-3 text-left transition-colors hover:bg-blue-50"
              @click="openArticleById(article.id)"
            >
              <div class="flex flex-wrap items-center gap-2">
                <span
                  class="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-700"
                >
                  {{ formatCategory(article.category) }}
                </span>
                <span
                  class="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-medium text-blue-700"
                >
                  {{ article.source }}
                </span>
                <span class="text-xs text-gray-400">{{ article.date }}</span>
              </div>
              <div class="mt-2 text-sm font-medium leading-6 text-gray-800">
                {{ article.title }}
              </div>
              <p v-if="article.summary" class="mt-1 text-xs leading-5 text-gray-500">
                {{ article.summary }}
              </p>
            </button>
          </div>
        </section>
      </article>

      <article v-else-if="selectedArticle" class="p-4">
        <div class="rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
          <div class="mb-4 flex flex-wrap items-center gap-2">
            <span class="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
              {{ formatCategory(selectedArticle.category) }}
            </span>
            <span class="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
              {{ formatSourceLabel(selectedArticle) }}
            </span>
            <span class="rounded-full bg-gray-100 px-2.5 py-1 text-xs text-gray-500">
              {{ selectedArticle.date }}
            </span>
          </div>

          <h4 class="text-lg font-semibold leading-7 text-gray-900">
            {{ selectedArticle.title }}
          </h4>
          <p class="mt-3 text-sm leading-6 text-gray-500">
            {{ selectedArticle.summary }}
          </p>

          <div class="my-5 h-px bg-gray-100" />

          <p class="whitespace-pre-line text-sm leading-7 text-gray-700">
            {{ selectedArticle.content }}
          </p>

          <a
            v-if="isSafeExternalUrl(selectedArticle.url)"
            :href="selectedArticle.url"
            target="_blank"
            rel="noopener noreferrer"
            class="mt-5 flex items-start gap-3 rounded-lg border border-gray-100 bg-gray-50 px-3 py-3 text-sm transition-colors hover:border-blue-200 hover:bg-blue-50/50"
          >
            <ExternalLink class="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-500" />
            <span class="min-w-0 flex-1">
              <span class="block truncate font-medium text-gray-700">
                {{ selectedArticle.source }}
              </span>
              <span class="mt-0.5 block truncate text-xs text-gray-400">
                {{ selectedArticle.url }}
              </span>
            </span>
          </a>
        </div>
      </article>
    </div>

    <div
      v-else-if="loading && displayItems.length === 0"
      class="flex flex-1 items-center justify-center p-8"
    >
      <div class="flex items-center gap-2 text-sm text-gray-400">
        <Loader2 class="h-4 w-4 animate-spin" />
        Loading campus news...
      </div>
    </div>

    <div
      v-else-if="displayItems.length === 0"
      class="flex flex-1 flex-col items-center px-8 py-16 text-center"
    >
      <div class="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gray-100">
        <Newspaper class="h-8 w-8 text-gray-300" />
      </div>
      <h4 class="text-base font-semibold text-gray-700">No news yet</h4>
      <p class="mt-2 max-w-xs text-sm leading-6 text-gray-400">
        {{ emptyMessage }}
      </p>
    </div>

    <div v-else class="space-y-3 p-4">
      <button
        v-if="dailyReport"
        type="button"
        class="group block w-full rounded-xl border border-blue-100 bg-blue-50/70 p-4 text-left shadow-sm transition-all hover:border-blue-200 hover:bg-blue-50 hover:shadow-md"
        @click="selectedReport = dailyReport"
      >
        <div class="mb-3 flex items-center justify-between gap-3">
          <span class="rounded-full bg-blue-100 px-2.5 py-1 text-[11px] font-medium text-blue-700">
            Daily Report
          </span>
          <span class="text-xs text-blue-400">{{ dailyReport.generated_at }}</span>
        </div>
        <h4 class="text-sm font-semibold leading-6 text-gray-900">
          {{ dailyReport.title }}
        </h4>
        <p class="mt-2 text-sm leading-6 text-gray-600">
          {{ dailyReport.summary }}
        </p>
        <div class="mt-3 flex items-center gap-1 text-xs font-medium text-blue-600">
          Open report
          <ExternalLink class="h-3.5 w-3.5" />
        </div>
      </button>

      <button
        v-for="article in articles"
        :key="article.id"
        type="button"
        class="group block w-full rounded-xl border border-gray-100 bg-white p-4 text-left shadow-sm transition-all hover:border-blue-200 hover:shadow-md"
        @click="openArticle(article)"
      >
        <div class="mb-3 flex items-center justify-between gap-3">
          <div class="flex min-w-0 flex-wrap items-center gap-2">
            <span
              class="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-700"
            >
              {{ formatCategory(article.category) }}
            </span>
            <span
              class="truncate rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-medium text-blue-700"
            >
              {{ formatSourceLabel(article) }}
            </span>
          </div>
          <span class="text-xs text-gray-400">{{ article.date }}</span>
        </div>
        <h4 class="text-sm font-semibold leading-6 text-gray-900">
          {{ article.title || 'Untitled campus update' }}
        </h4>
        <p v-if="article.summary" class="mt-2 text-sm leading-6 text-gray-500">
          {{ article.summary }}
        </p>
        <div
          class="mt-3 flex items-center gap-1 text-xs font-medium text-blue-600 opacity-0 transition-opacity group-hover:opacity-100"
        >
          Read details
          <ExternalLink class="h-3.5 w-3.5" />
        </div>
      </button>

      <article
        v-for="(item, index) in articles.length === 0 ? displayItems : []"
        :key="`${item.title || 'news'}-${index}`"
        class="group rounded-xl border border-gray-100 bg-white p-4 shadow-sm transition-all hover:border-blue-200 hover:shadow-md"
      >
        <div class="mb-3 flex items-center justify-between gap-3">
          <div class="flex min-w-0 flex-wrap items-center gap-2">
            <span
              class="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-700"
            >
              {{ formatCategory(item.category) }}
            </span>
            <span
              class="truncate rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-medium text-blue-700"
            >
              {{ formatSourceLabel(item) }}
            </span>
          </div>
          <Sparkles class="h-4 w-4 text-gray-300 transition-colors group-hover:text-amber-400" />
        </div>
        <h4 class="text-sm font-semibold leading-6 text-gray-900">
          {{ item.title || 'Untitled campus update' }}
        </h4>
        <p v-if="item.summary" class="mt-2 text-sm leading-6 text-gray-500">
          {{ item.summary }}
        </p>
      </article>
    </div>

    <div v-if="sourceItems.length > 0" class="mt-auto border-t border-gray-200 bg-white p-4">
      <div class="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-gray-400">
        Sources
      </div>
      <div class="space-y-2">
        <template
          v-for="(source, index) in sourceItems"
          :key="`${source.title || 'source'}-${index}`"
        >
          <a
            v-if="isSafeExternalUrl(source.url)"
            :href="source.url"
            target="_blank"
            rel="noopener noreferrer"
            class="flex items-start gap-3 rounded-lg border border-gray-100 bg-gray-50 px-3 py-3 text-sm transition-colors hover:border-blue-200 hover:bg-blue-50/50"
          >
            <ExternalLink class="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-500" />
            <span class="min-w-0 flex-1">
              <span class="block truncate font-medium text-gray-700">
                {{ source.title || 'Campus news source' }}
              </span>
              <span v-if="source.source" class="mt-0.5 block truncate text-xs text-gray-400">
                {{ formatSourceLabel(source) }}
              </span>
            </span>
          </a>
          <div
            v-else
            class="flex items-start gap-3 rounded-lg border border-gray-100 bg-gray-50 px-3 py-3 text-sm"
          >
            <FileText class="mt-0.5 h-4 w-4 flex-shrink-0 text-gray-400" />
            <span class="min-w-0 flex-1">
              <span class="block truncate font-medium text-gray-700">
                {{ source.title || 'Campus news source' }}
              </span>
              <span v-if="source.source" class="mt-0.5 block truncate text-xs text-gray-400">
                {{ formatSourceLabel(source) }}
              </span>
            </span>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>
