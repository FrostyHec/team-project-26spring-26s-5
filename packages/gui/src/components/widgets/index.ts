/**
 * Widget component registry — maps WidgetType values to async Vue
 * components and display titles.
 *
 * New widgets only need to add an entry here and drop a `.vue` file
 * in this directory; {@link WorkspacePanel} reads the registry at
 * runtime so it never needs a manual switch-case update.
 */

import { defineAsyncComponent, type Component } from 'vue'
import { WIDGET_TYPES, type WidgetType } from '@/stores/chatConstants'

/** Lazy-loaded Vue component per widget type. */
export const WIDGET_COMPONENTS: Record<WidgetType, Component> = {
  [WIDGET_TYPES.CALENDAR]: defineAsyncComponent(() => import('./CalendarWidget.vue')),
  [WIDGET_TYPES.DOCUMENT]: defineAsyncComponent(() => import('./DocumentWidget.vue')),
  [WIDGET_TYPES.COURSE_CARDS]: defineAsyncComponent(() => import('./CourseCardsWidget.vue')),
  [WIDGET_TYPES.SOURCES]: defineAsyncComponent(() => import('./SourcesWidget.vue')),
  [WIDGET_TYPES.WEB_PREVIEW]: defineAsyncComponent(() => import('./WebPreviewWidget.vue')),
  [WIDGET_TYPES.NEWS_DIGEST]: defineAsyncComponent(() => import('./EmptyWidget.vue')),
  [WIDGET_TYPES.INBOX]: defineAsyncComponent(() => import('./EmptyWidget.vue')),
  [WIDGET_TYPES.EMPTY]: defineAsyncComponent(() => import('./EmptyWidget.vue')),
}

/** Human-readable titles shown in the WorkspacePanel header. */
export const WIDGET_TITLES: Record<WidgetType, string> = {
  [WIDGET_TYPES.CALENDAR]: 'Calendar',
  [WIDGET_TYPES.DOCUMENT]: 'Document',
  [WIDGET_TYPES.COURSE_CARDS]: 'Courses',
  [WIDGET_TYPES.SOURCES]: 'Sources',
  [WIDGET_TYPES.WEB_PREVIEW]: 'Web Preview',
  [WIDGET_TYPES.NEWS_DIGEST]: 'News Digest',
  [WIDGET_TYPES.INBOX]: 'Inbox',
  [WIDGET_TYPES.EMPTY]: 'Workspace',
}
