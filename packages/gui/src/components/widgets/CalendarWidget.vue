<script setup lang="ts">
import { Calendar, Clock, AlertCircle } from 'lucide-vue-next'

interface CalendarEvent {
  title: string
  date?: string
  time?: string
  priority?: 'high' | 'medium' | 'low'
  course?: string
}

const props = defineProps<{
  data: Record<string, unknown>
}>()

const events: CalendarEvent[] = Array.isArray(props.data.events)
  ? (props.data.events as CalendarEvent[])
  : []

function priorityDot(priority?: string): string {
  switch (priority) {
    case 'high':
      return 'bg-red-500'
    case 'medium':
      return 'bg-yellow-500'
    default:
      return 'bg-green-500'
  }
}
</script>

<template>
  <div class="p-4">
    <div class="flex items-center gap-2 mb-4">
      <Calendar class="w-5 h-5 text-blue-600" />
      <h3 class="font-semibold text-gray-800">Upcoming Deadlines</h3>
    </div>

    <div v-if="events.length === 0" class="text-center py-8 text-gray-400">
      <Calendar class="w-10 h-10 mx-auto mb-2 opacity-50" />
      <p class="text-sm">No upcoming events</p>
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="(evt, i) in events"
        :key="i"
        class="flex items-start gap-3 p-3 bg-white rounded-lg border border-gray-100 shadow-sm hover:shadow-md transition-shadow"
      >
        <!-- Priority indicator -->
        <div class="flex flex-col items-center pt-1">
          <span class="w-2.5 h-2.5 rounded-full" :class="priorityDot(evt.priority)" />
          <div v-if="i < events.length - 1" class="w-px h-6 bg-gray-200 mt-1" />
        </div>

        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-gray-800 truncate">{{ evt.title }}</p>
          <div class="flex items-center gap-3 mt-1 text-xs text-gray-500">
            <span v-if="evt.date" class="flex items-center gap-1">
              <Calendar class="w-3 h-3" />
              {{ evt.date }}
            </span>
            <span v-if="evt.time" class="flex items-center gap-1">
              <Clock class="w-3 h-3" />
              {{ evt.time }}
            </span>
          </div>
          <span
            v-if="evt.course"
            class="inline-block mt-1 px-2 py-0.5 bg-blue-50 text-blue-600 text-xs rounded-full"
          >
            {{ evt.course }}
          </span>
        </div>

        <AlertCircle
          v-if="evt.priority === 'high'"
          class="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5"
        />
      </div>
    </div>
  </div>
</template>
