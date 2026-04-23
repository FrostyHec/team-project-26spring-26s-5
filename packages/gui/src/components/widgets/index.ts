/**
 * Widget component registry — maps WidgetType values to async Vue
 * components and i18n title keys.
 *
 * New widgets only need to add an entry here and drop a `.vue` file
 * in this directory; {@link WorkspacePanel} reads the registry at
 * runtime so it never needs a manual switch-case update.
 */

import { defineAsyncComponent, type Component } from 'vue'
import { WIDGET_TYPES, type WidgetType } from '@/stores/chatConstants'

/** Lazy-loaded Vue component per widget type. */
export const WIDGET_COMPONENTS: Record<WidgetType, Component> = {
  [WIDGET_TYPES.CALENDAR]: defineAsyncComponent(() => import('./DeadlinePanelWidget.vue')),
  [WIDGET_TYPES.DOCUMENT]: defineAsyncComponent(() => import('./DocumentWidget.vue')),
  [WIDGET_TYPES.COURSE_CARDS]: defineAsyncComponent(() => import('./CourseCardsWidget.vue')),
  [WIDGET_TYPES.SOURCES]: defineAsyncComponent(() => import('./SourcesWidget.vue')),
  [WIDGET_TYPES.WEB_PREVIEW]: defineAsyncComponent(() => import('./WebPreviewWidget.vue')),
  [WIDGET_TYPES.NEWS_DIGEST]: defineAsyncComponent(() => import('./EmptyWidget.vue')),
  [WIDGET_TYPES.QUIZ]: defineAsyncComponent(() => import('./CourseCardsWidget.vue')),
  [WIDGET_TYPES.DOCUMENT_ANALYSIS]: defineAsyncComponent(() => import('./CourseCardsWidget.vue')),
  [WIDGET_TYPES.INBOX]: defineAsyncComponent(() => import('./InboxWidget.vue')),
  [WIDGET_TYPES.EMPTY]: defineAsyncComponent(() => import('./EmptyWidget.vue')),
  [WIDGET_TYPES.POLICY_SEARCH]: defineAsyncComponent(() => import('./PolicySearchWidget.vue')),
}

/** i18n key for each widget title, resolved at runtime via t(). */
export const WIDGET_TITLE_I18N_KEYS: Record<WidgetType, string> = {
  [WIDGET_TYPES.CALENDAR]: 'widgets.calendar',
  [WIDGET_TYPES.DOCUMENT]: 'widgets.document',
  [WIDGET_TYPES.COURSE_CARDS]: 'widgets.courses',
  [WIDGET_TYPES.SOURCES]: 'widgets.sources',
  [WIDGET_TYPES.WEB_PREVIEW]: 'widgets.webPreview',
  [WIDGET_TYPES.NEWS_DIGEST]: 'widgets.newsDigest',
  [WIDGET_TYPES.INBOX]: 'widgets.inbox',
  [WIDGET_TYPES.EMPTY]: 'widgets.empty',
  [WIDGET_TYPES.QUIZ]: 'widgets.quiz',
  [WIDGET_TYPES.DOCUMENT_ANALYSIS]: 'widgets.documentAnalysis',
  [WIDGET_TYPES.POLICY_SEARCH]: 'widgets.policySearch',
}

/**
 * Widget types that should appear in the user-facing selector dropdown.
 * Excludes stub/empty widgets that have no real implementation yet.
 */
const HIDDEN_WIDGET_TYPES: ReadonlySet<WidgetType> = new Set([
  WIDGET_TYPES.EMPTY,
  WIDGET_TYPES.NEWS_DIGEST,
  WIDGET_TYPES.QUIZ,
  WIDGET_TYPES.DOCUMENT_ANALYSIS,
])

/** A selectable widget entry for the dropdown. */
export interface SelectableWidget {
  type: WidgetType
  titleKey: string
}

/** Ordered list of widgets available in the selector dropdown. */
export const SELECTABLE_WIDGETS: SelectableWidget[] = (
  Object.keys(WIDGET_TITLE_I18N_KEYS) as WidgetType[]
)
  .filter((t) => !HIDDEN_WIDGET_TYPES.has(t))
  .map((t) => ({ type: t, titleKey: WIDGET_TITLE_I18N_KEYS[t] }))
