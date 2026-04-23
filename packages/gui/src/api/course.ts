/**
 * API client for course and course-material endpoints.
 * Communicates with ``/courses`` and ``/course-materials`` endpoints.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

const COURSES_ENDPOINT = `${API_BASE}/courses`
const MATERIALS_ENDPOINT = `${API_BASE}/course-materials`

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Persistent course record (mirrors backend Course SQLModel). */
export interface Course {
  id: string
  name: string
  code: string
  credits: number | null
  instructor: string
  description: string
  tags: string
  semester: string
  created_at: string
  updated_at: string
}

/** Fields accepted when creating a new course. */
export interface CourseCreate {
  name: string
  code?: string
  credits?: number | null
  instructor?: string
  description?: string
  tags?: string
  semester?: string
}

/** Fields accepted when updating an existing course. */
export interface CourseUpdate {
  name?: string
  code?: string
  credits?: number | null
  instructor?: string
  description?: string
  tags?: string
  semester?: string
}

/** Persistent course material record (mirrors backend CourseMaterial SQLModel). */
export interface CourseMaterial {
  id: string
  course_id: string
  filename: string
  stored_path: string
  file_type: string
  file_size: number
  description: string
  tags: string
  created_at: string
}

/** Fields accepted when updating an existing material. */
export interface MaterialUpdate {
  description?: string
  tags?: string
}

// ---------------------------------------------------------------------------
// Courses
// ---------------------------------------------------------------------------

/** Fetch all courses, optionally filtered by semester. */
export async function listCourses(semester?: string): Promise<Course[]> {
  const url = semester
    ? `${COURSES_ENDPOINT}?semester=${encodeURIComponent(semester)}`
    : COURSES_ENDPOINT
  const response = await fetch(url, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`Failed to list courses: ${response.status}`)
  }
  const data = (await response.json()) as { courses: Course[] }
  return data.courses
}

/** Fetch a single course by ID. */
export async function getCourse(id: string): Promise<Course> {
  const response = await fetch(`${COURSES_ENDPOINT}/${encodeURIComponent(id)}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`Failed to get course ${id}: ${response.status}`)
  }
  return (await response.json()) as Course
}

/** Create a new course. */
export async function createCourse(body: CourseCreate): Promise<Course> {
  const response = await fetch(COURSES_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const bodyText = await response.text()
    throw new Error(`Failed to create course: ${response.status} ${bodyText}`)
  }
  return (await response.json()) as Course
}

/** Update an existing course. */
export async function updateCourse(id: string, body: CourseUpdate): Promise<Course> {
  const response = await fetch(`${COURSES_ENDPOINT}/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const bodyText = await response.text()
    throw new Error(`Failed to update course ${id}: ${response.status} ${bodyText}`)
  }
  return (await response.json()) as Course
}

/** Delete a course by ID. */
export async function deleteCourse(id: string): Promise<void> {
  const response = await fetch(`${COURSES_ENDPOINT}/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`Failed to delete course ${id}: ${response.status}`)
  }
}

// ---------------------------------------------------------------------------
// Course Materials
// ---------------------------------------------------------------------------

/** Fetch all materials, optionally filtered by course. */
export async function listMaterials(courseId?: string): Promise<CourseMaterial[]> {
  const url = courseId
    ? `${MATERIALS_ENDPOINT}?course_id=${encodeURIComponent(courseId)}`
    : MATERIALS_ENDPOINT
  const response = await fetch(url, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`Failed to list materials: ${response.status}`)
  }
  const data = (await response.json()) as { materials: CourseMaterial[] }
  return data.materials
}

/** Fetch a single material by ID. */
export async function getMaterial(id: string): Promise<CourseMaterial> {
  const response = await fetch(`${MATERIALS_ENDPOINT}/${encodeURIComponent(id)}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`Failed to get material ${id}: ${response.status}`)
  }
  return (await response.json()) as CourseMaterial
}

/**
 * Upload a file and attach it to a course.
 *
 * @param file - The file to upload.
 * @param courseId - The owning course ID.
 * @param description - Optional description.
 * @param tags - Optional tags.
 * @returns The created CourseMaterial record.
 * @throws Error on validation failure (422) or server error.
 */
export async function uploadMaterial(
  file: File,
  courseId: string,
  description = '',
  tags = '',
): Promise<CourseMaterial> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('course_id', courseId)
  formData.append('description', description)
  formData.append('tags', tags)

  const response = await fetch(MATERIALS_ENDPOINT, {
    method: 'POST',
    body: formData,
  })
  if (!response.ok) {
    const bodyText = await response.text()
    throw new Error(`Failed to upload material: ${response.status} ${bodyText}`)
  }
  return (await response.json()) as CourseMaterial
}

/** Update description and/or tags of a material. */
export async function updateMaterial(id: string, body: MaterialUpdate): Promise<CourseMaterial> {
  const formData = new FormData()
  if (body.description !== undefined) formData.append('description', body.description)
  if (body.tags !== undefined) formData.append('tags', body.tags)

  const response = await fetch(`${MATERIALS_ENDPOINT}/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: formData,
  })
  if (!response.ok) {
    const bodyText = await response.text()
    throw new Error(`Failed to update material ${id}: ${response.status} ${bodyText}`)
  }
  return (await response.json()) as CourseMaterial
}

/** Delete a material by ID (record + physical file). */
export async function deleteMaterial(id: string): Promise<void> {
  const response = await fetch(`${MATERIALS_ENDPOINT}/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`Failed to delete material ${id}: ${response.status}`)
  }
}

/**
 * Trigger a download of a material's file.
 * Opens the file in a new tab or triggers a browser download.
 */
export function downloadMaterialUrl(id: string): string {
  return `${MATERIALS_ENDPOINT}/${encodeURIComponent(id)}/download`
}
