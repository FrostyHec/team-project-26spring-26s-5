<script setup lang="ts">
/**
 * CourseManager — course CRUD widget.
 *
 * Displays a list of courses with add / edit / delete actions.
 * When a course is selected, emits `select-course` so the parent
 * can switch to the FileManager view.
 */

import { ref, onMounted } from 'vue'
import { BookOpen, Plus, Pencil, Trash2, ChevronRight } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { useCourseStore } from '@/stores/courseStore'
import type { Course, CourseCreate } from '@/stores/courseStore'

const { t } = useI18n()
const store = useCourseStore()

// ---------- Lifecycle ----------

onMounted(() => {
  store.fetchCourses()
})

// ---------- Modal state ----------

type ModalMode = 'add' | 'edit'

const showModal = ref(false)
const modalMode = ref<ModalMode>('add')
const editingCourse = ref<Course | null>(null)

const form = ref<CourseCreate>({
  name: '',
  code: '',
  credits: null,
  instructor: '',
  description: '',
  tags: '',
  semester: '',
})

function openAddModal() {
  modalMode.value = 'add'
  editingCourse.value = null
  form.value = {
    name: '',
    code: '',
    credits: null,
    instructor: '',
    description: '',
    tags: '',
    semester: '',
  }
  showModal.value = true
}

function openEditModal(course: Course) {
  modalMode.value = 'edit'
  editingCourse.value = course
  form.value = {
    name: course.name,
    code: course.code,
    credits: course.credits,
    instructor: course.instructor,
    description: course.description,
    tags: course.tags,
    semester: course.semester,
  }
  showModal.value = true
}

async function handleSave() {
  if (!form.value.name.trim()) return
  if (modalMode.value === 'edit' && editingCourse.value) {
    await store.editCourse(editingCourse.value.id, form.value)
  } else {
    await store.addCourse(form.value)
  }
  if (!store.error) {
    showModal.value = false
  }
}

// ---------- Delete ----------

const confirmDeleteId = ref<string | null>(null)

function confirmDelete(course: Course) {
  confirmDeleteId.value = course.id
}

async function handleDelete() {
  if (!confirmDeleteId.value) return
  await store.removeCourse(confirmDeleteId.value)
  confirmDeleteId.value = null
}

// ---------- Select course ----------

const emit = defineEmits<{
  (e: 'select-course', course: Course): void
}>()

function handleSelect(course: Course) {
  emit('select-course', course)
}
</script>

<template>
  <div class="flex flex-col h-full bg-gray-50">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 bg-white border-b border-gray-100">
      <h2 class="text-sm font-semibold text-gray-700 flex items-center gap-2">
        <BookOpen class="w-4 h-4 text-blue-500" />
        {{ t('courseManager.myCourses') }}
      </h2>
      <button
        class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-blue-500 rounded-md hover:bg-blue-600 transition-colors"
        @click="openAddModal"
      >
        <Plus class="w-3.5 h-3.5" />
        {{ t('courseManager.addCourse') }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="store.isLoadingCourses" class="flex items-center justify-center flex-1 py-8">
      <span class="text-sm text-gray-400">{{ t('courseManager.loading') }}</span>
    </div>

    <!-- Empty -->
    <div
      v-else-if="store.courses.length === 0"
      class="flex flex-col items-center justify-center flex-1 py-8 text-gray-400"
    >
      <BookOpen class="w-10 h-10 mb-2 opacity-40" />
      <p class="text-sm">{{ t('courseManager.emptyCourses') }}</p>
      <p class="text-xs mt-1">{{ t('courseManager.emptyCoursesHint') }}</p>
    </div>

    <!-- Course list -->
    <div v-else class="flex-1 overflow-y-auto">
      <div
        v-for="course in store.courses"
        :key="course.id"
        class="flex items-center gap-3 px-4 py-3 bg-white border-b border-gray-50 hover:bg-gray-50 transition-colors group"
      >
        <!-- Course icon + info -->
        <div
          class="flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center"
          :style="{ backgroundColor: '#3b82f620', color: '#3b82f6' }"
        >
          <BookOpen class="w-4 h-4" />
        </div>

        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-gray-800 truncate">{{ course.name }}</p>
          <p class="text-xs text-gray-400 truncate">
            <span v-if="course.code">{{ course.code }}</span>
            <span v-if="course.code && course.instructor"> · </span>
            <span v-if="course.instructor">{{ course.instructor }}</span>
            <span v-if="course.credits !== null">
              · {{ course.credits }}{{ t('courseManager.creditsLabel') }}</span
            >
          </p>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            class="p-1.5 rounded-md text-gray-400 hover:text-blue-500 hover:bg-blue-50 transition-colors"
            :title="t('courseManager.editCourse')"
            @click.stop="openEditModal(course)"
          >
            <Pencil class="w-3.5 h-3.5" />
          </button>
          <button
            class="p-1.5 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
            :title="t('courseManager.deleteCourse')"
            @click.stop="confirmDelete(course)"
          >
            <Trash2 class="w-3.5 h-3.5" />
          </button>
        </div>

        <!-- Select -->
        <button
          class="flex-shrink-0 p-1.5 rounded-md text-gray-300 hover:text-blue-500 transition-colors"
          :title="t('courseManager.learning')"
          @click.stop="handleSelect(course)"
        >
          <ChevronRight class="w-4 h-4" />
        </button>
      </div>
    </div>

    <!-- Add / Edit Modal -->
    <div
      v-if="showModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
      @click.self="showModal = false"
    >
      <div class="w-full max-w-md bg-white rounded-xl shadow-xl overflow-hidden">
        <div class="px-5 pt-5 pb-4 border-b border-gray-100">
          <h3 class="text-base font-semibold text-gray-800">
            {{ modalMode === 'add' ? t('courseManager.addCourse') : t('courseManager.editCourse') }}
          </h3>
        </div>

        <div class="px-5 py-4 space-y-3 max-h-[60vh] overflow-y-auto">
          <!-- Course name -->
          <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">
              {{ t('courseManager.nameLabel') }} *
            </label>
            <input
              v-model="form.name"
              type="text"
              :placeholder="t('courseManager.namePlaceholder')"
              class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <!-- Code + Credits row -->
          <div class="flex gap-3">
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-500 mb-1">{{
                t('courseManager.codeLabel')
              }}</label>
              <input
                v-model="form.code"
                type="text"
                :placeholder="t('courseManager.codePlaceholder')"
                class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div class="w-24">
              <label class="block text-xs font-medium text-gray-500 mb-1">{{
                t('courseManager.creditsLabel')
              }}</label>
              <input
                v-model.number="form.credits"
                type="number"
                min="0"
                step="0.5"
                class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <!-- Instructor -->
          <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">{{
              t('courseManager.instructorLabel')
            }}</label>
            <input
              v-model="form.instructor"
              type="text"
              :placeholder="t('courseManager.instructorPlaceholder')"
              class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <!-- Semester -->
          <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">{{
              t('courseManager.semesterLabel')
            }}</label>
            <input
              v-model="form.semester"
              type="text"
              :placeholder="t('courseManager.semesterPlaceholder')"
              class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <!-- Description -->
          <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">{{
              t('courseManager.descriptionLabel')
            }}</label>
            <textarea
              v-model="form.description"
              :placeholder="t('courseManager.descriptionPlaceholder')"
              rows="2"
              class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
          </div>

          <!-- Tags -->
          <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">{{
              t('courseManager.tagsLabel')
            }}</label>
            <input
              v-model="form.tags"
              type="text"
              :placeholder="t('courseManager.tagsPlaceholder')"
              class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <!-- Error -->
          <p v-if="store.error" class="text-xs text-red-500">{{ store.error }}</p>
        </div>

        <div class="px-5 pb-5 flex justify-end gap-2">
          <button
            class="px-4 py-2 text-sm text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
            @click="showModal = false"
          >
            {{ t('courseManager.cancel') }}
          </button>
          <button
            class="px-4 py-2 text-sm font-medium text-white bg-blue-500 rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50"
            :disabled="!form.name.trim()"
            @click="handleSave"
          >
            {{ t('courseManager.save') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Confirm Modal -->
    <div
      v-if="confirmDeleteId !== null"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
      @click.self="confirmDeleteId = null"
    >
      <div class="w-full max-w-sm bg-white rounded-xl shadow-xl overflow-hidden p-6">
        <h3 class="text-base font-semibold text-gray-800 mb-2">
          {{ t('courseManager.deleteCourse') }}
        </h3>
        <p class="text-sm text-gray-500 mb-5">
          {{
            t('courseManager.confirmDeleteCourse', {
              name: store.courses.find((c) => c.id === confirmDeleteId)?.name ?? '',
            })
          }}
        </p>
        <div class="flex justify-end gap-2">
          <button
            class="px-4 py-2 text-sm text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
            @click="confirmDeleteId = null"
          >
            {{ t('courseManager.cancel') }}
          </button>
          <button
            class="px-4 py-2 text-sm font-medium text-white bg-red-500 rounded-lg hover:bg-red-600 transition-colors"
            @click="handleDelete"
          >
            {{ t('courseManager.deleteCourse') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
