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
}
