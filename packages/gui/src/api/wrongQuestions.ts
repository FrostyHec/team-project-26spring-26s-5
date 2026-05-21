/**
 * API client for wrong question book.
 */

import type { QuizQuestion } from '@/components/widgets/types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export interface WrongQuestion {
  id: number
  question_id: number
  question_type: 'multiple_choice' | 'true_false' | 'fill_blank' | 'short_answer'
  question: string
  options: string[] | null
  correct_answer: string
  explanation: string | null
  source_session_id: string | null
  created_at: string
}

export interface WrongQuestionCreate {
  question_id: number
  question_type: 'multiple_choice' | 'true_false' | 'fill_blank' | 'short_answer'
  question: string
  options: string[] | null
  correct_answer: string
  explanation: string | null
  source_session_id?: string | null
}

export interface WrongQuestionListResponse {
  questions: WrongQuestion[]
}

export async function addWrongQuestion(data: WrongQuestionCreate): Promise<WrongQuestion> {
  const response = await fetch(`${API_BASE}/wrong-questions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to add wrong question: ${response.statusText}`)
  }
  return response.json()
}

export async function getWrongQuestions(type?: string): Promise<WrongQuestionListResponse> {
  const url = new URL(`${API_BASE}/wrong-questions`, window.location.origin)
  if (type) {
    url.searchParams.set('type', type)
  }
  const response = await fetch(url.toString())
  if (!response.ok) {
    throw new Error(`Failed to get wrong questions: ${response.statusText}`)
  }
  return response.json()
}

export async function deleteWrongQuestion(id: number): Promise<void> {
  const response = await fetch(`${API_BASE}/wrong-questions/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete wrong question: ${response.statusText}`)
  }
}

/** Convert WrongQuestion to QuizQuestion for evaluation. */
export function wrongQuestionToQuizQuestion(wq: WrongQuestion): QuizQuestion {
  return {
    id: wq.id,
    type: wq.question_type,
    question: wq.question,
    options: wq.options,
    correct_answer: wq.correct_answer,
    explanation: wq.explanation,
  }
}
