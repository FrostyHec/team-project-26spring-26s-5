/**
 * Pinia store for course and course-material management.
 *
 * Manages the list of courses and the currently selected course's materials.
 */

import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import {
  listCourses,
  createCourse,
  updateCourse,
  deleteCourse,
  listMaterials,
  uploadMaterial,
  updateMaterial,
  deleteMaterial,
  downloadMaterialUrl,
  type Course,
  type CourseCreate,
  type CourseUpdate,
  type CourseMaterial,
  type MaterialUpdate,
} from '@/api/course'

export type { Course, CourseCreate, CourseUpdate, CourseMaterial, MaterialUpdate }

export const useCourseStore = defineStore('course', () => {
  // ---------- State ----------

  /** All known courses. */
  const courses = ref<Course[]>([])

  /** Materials belonging to the currently selected course. */
  const materials = ref<CourseMaterial[]>([])

  /** ID of the course whose materials are currently loaded in `materials`. */
  const selectedCourseId = ref<string | null>(null)

  /** True while loading courses. */
  const isLoadingCourses = ref(false)

  /** True while loading materials. */
  const isLoadingMaterials = ref(false)

  /** True while uploading a file. */
  const isUploading = ref(false)

  /** Error from the last failed operation, or null. */
  const error = ref<string | null>(null)

  // ---------- Computed ----------

  /** Whether any course has been selected. */
  const hasSelectedCourse = computed(() => selectedCourseId.value !== null)

  // ---------- Actions ----------

  /** Fetch all courses from the backend. */
  async function fetchCourses(semester?: string): Promise<void> {
    isLoadingCourses.value = true
    error.value = null
    try {
      courses.value = await listCourses(semester)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load courses'
    } finally {
      isLoadingCourses.value = false
    }
  }

  /** Add a new course. */
  async function addCourse(body: CourseCreate): Promise<Course | null> {
    error.value = null
    try {
      const created = await createCourse(body)
      courses.value.push(created)
      return created
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to create course'
      return null
    }
  }

  /** Update an existing course. */
  async function editCourse(id: string, body: CourseUpdate): Promise<Course | null> {
    error.value = null
    try {
      const updated = await updateCourse(id, body)
      const idx = courses.value.findIndex((c) => c.id === id)
      if (idx !== -1) courses.value[idx] = updated
      return updated
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to update course'
      return null
    }
  }

  /** Delete a course by ID. */
  async function removeCourse(id: string): Promise<boolean> {
    error.value = null
    try {
      await deleteCourse(id)
      courses.value = courses.value.filter((c) => c.id !== id)
      if (selectedCourseId.value === id) {
        selectedCourseId.value = null
        materials.value = []
      }
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to delete course'
      return false
    }
  }

  /** Load materials for a given course and mark it as selected. */
  async function selectCourse(courseId: string): Promise<void> {
    if (selectedCourseId.value === courseId && materials.value.length > 0) return
    selectedCourseId.value = courseId
    await fetchMaterials(courseId)
  }

  /** Clear the selected course and its materials. */
  function clearSelection(): void {
    selectedCourseId.value = null
    materials.value = []
  }

  /** Fetch materials for a given course (does not change `selectedCourseId`). */
  async function fetchMaterials(courseId: string): Promise<void> {
    isLoadingMaterials.value = true
    error.value = null
    try {
      materials.value = await listMaterials(courseId)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load materials'
    } finally {
      isLoadingMaterials.value = false
    }
  }

  /** Upload a file to the currently selected course. */
  async function addMaterial(
    file: File,
    description = '',
    tags = '',
  ): Promise<CourseMaterial | null> {
    if (!selectedCourseId.value) {
      error.value = 'No course selected'
      return null
    }
    isUploading.value = true
    error.value = null
    try {
      const created = await uploadMaterial(file, selectedCourseId.value, description, tags)
      materials.value.push(created)
      return created
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to upload file'
      return null
    } finally {
      isUploading.value = false
    }
  }

  /** Update description and/or tags of a material. */
  async function editMaterial(id: string, body: MaterialUpdate): Promise<CourseMaterial | null> {
    error.value = null
    try {
      const updated = await updateMaterial(id, body)
      const idx = materials.value.findIndex((m) => m.id === id)
      if (idx !== -1) materials.value[idx] = updated
      return updated
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to update material'
      return null
    }
  }

  /** Delete a material by ID. */
  async function removeMaterial(id: string): Promise<boolean> {
    error.value = null
    try {
      await deleteMaterial(id)
      materials.value = materials.value.filter((m) => m.id !== id)
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to delete material'
      return false
    }
  }

  /** Return the download URL for a material. */
  function getDownloadUrl(id: string): string {
    return downloadMaterialUrl(id)
  }

  /** Clear the current error. */
  function clearError(): void {
    error.value = null
  }

  return {
    // State
    courses,
    materials,
    selectedCourseId,
    isLoadingCourses,
    isLoadingMaterials,
    isUploading,
    error,
    // Computed
    hasSelectedCourse,
    // Actions
    fetchCourses,
    addCourse,
    editCourse,
    removeCourse,
    selectCourse,
    clearSelection,
    fetchMaterials,
    addMaterial,
    editMaterial,
    removeMaterial,
    getDownloadUrl,
    clearError,
  }
})
