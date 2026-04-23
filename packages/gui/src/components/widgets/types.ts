/**
 * Frontend types for course-related widgets.
 *
 * Course / CourseMaterial are the persistent backend types used by
 * the course management UI (CourseManager + FileManager).
 *
 * CourseInfo is the transient AI-generated type used by the quiz
 * course-recommendation accordion section.
 */

import type { Course, CourseMaterial } from '@/stores/courseStore'

export type { Course, CourseMaterial }

export interface CourseInfo {
  name: string
  code?: string
  credits?: number
  workload?: string
  rating?: number
  instructor?: string
  description?: string
}

export interface QuizQuestion {
  id: number
  type: 'multiple_choice' | 'true_false' | 'fill_blank' | 'short_answer'
  question: string
  options: string[] | null
  correct_answer: string
  explanation: string | null
  score?: number
  difficulty?: 'easy' | 'medium' | 'hard'
}
