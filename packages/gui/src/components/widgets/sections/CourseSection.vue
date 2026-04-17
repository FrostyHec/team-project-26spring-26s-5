<script setup lang="ts">
import { Clock, Star } from 'lucide-vue-next'
import type { CourseInfo } from '../types'

const props = defineProps<{
  courses: CourseInfo[]
}>()

function ratingStars(rating?: number): number {
  return Math.round(rating ?? 0)
}
</script>

<template>
  <div class="p-4 space-y-3">
    <div
      v-for="(course, i) in courses"
      :key="i"
      class="p-4 bg-white rounded-lg border border-slate-100 shadow-sm hover:shadow-md transition-shadow"
    >
      <div class="flex items-start justify-between mb-2">
        <div>
          <h4 class="text-sm font-semibold text-slate-800">{{ course.name }}</h4>
          <span v-if="course.code" class="text-xs text-slate-500">{{ course.code }}</span>
        </div>
        <span
          v-if="course.credits"
          class="px-2 py-0.5 bg-blue-50 text-blue-600 text-xs font-medium rounded-full"
        >
          {{ course.credits }} credits
        </span>
      </div>
      <p v-if="course.description" class="text-xs text-slate-500 mb-2 line-clamp-2">
        {{ course.description }}
      </p>
      <div class="flex items-center gap-3 text-xs text-slate-500">
        <span v-if="course.workload" class="flex items-center gap-1">
          <Clock class="w-3 h-3" />
          {{ course.workload }}
        </span>
        <span v-if="course.rating" class="flex items-center gap-0.5">
          <Star
            v-for="s in ratingStars(course.rating)"
            :key="s"
            class="w-3 h-3 text-yellow-400 fill-yellow-400"
          />
          <span class="ml-0.5">{{ course.rating }}</span>
        </span>
        <span v-if="course.instructor" class="text-slate-400">
          {{ course.instructor }}
        </span>
      </div>
    </div>
  </div>
</template>
