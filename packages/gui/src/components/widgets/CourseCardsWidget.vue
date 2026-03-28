<script setup lang="ts">
import { computed } from 'vue'
import { BookOpen, Clock, Star } from 'lucide-vue-next'

interface CourseInfo {
  name: string
  code?: string
  credits?: number
  workload?: string
  rating?: number
  instructor?: string
  description?: string
}

const props = defineProps<{
  data: Record<string, unknown>
}>()

const courses = computed<CourseInfo[]>(() =>
  Array.isArray(props.data.courses) ? (props.data.courses as CourseInfo[]) : [],
)

function ratingStars(rating?: number): number {
  return Math.round(rating ?? 0)
}
</script>

<template>
  <div class="p-4">
    <div class="flex items-center gap-2 mb-4">
      <BookOpen class="w-5 h-5 text-green-600" />
      <h3 class="font-semibold text-gray-800">Course Recommendations</h3>
    </div>

    <div v-if="courses.length === 0" class="text-center py-8 text-gray-400">
      <BookOpen class="w-10 h-10 mx-auto mb-2 opacity-50" />
      <p class="text-sm">No courses to display</p>
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="(course, i) in courses"
        :key="i"
        class="p-4 bg-white rounded-lg border border-green-100 shadow-sm hover:shadow-md transition-shadow"
      >
        <div class="flex items-start justify-between mb-2">
          <div>
            <h4 class="text-sm font-semibold text-gray-800">{{ course.name }}</h4>
            <span v-if="course.code" class="text-xs text-gray-500">{{ course.code }}</span>
          </div>
          <span
            v-if="course.credits"
            class="px-2 py-0.5 bg-green-100 text-green-700 text-xs font-medium rounded-full"
          >
            {{ course.credits }} credits
          </span>
        </div>

        <p v-if="course.description" class="text-xs text-gray-500 mb-2 line-clamp-2">
          {{ course.description }}
        </p>

        <div class="flex items-center gap-3 text-xs text-gray-500">
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
          <span v-if="course.instructor" class="text-gray-400">
            {{ course.instructor }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
