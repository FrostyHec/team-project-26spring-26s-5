/**
 * Unit tests for ChatInputBox logic utilities.
 * Tests the mention detection and IME-safe keyboard handling logic
 * in isolation, without mounting the full Vue component.
 */
import { describe, it, expect } from 'vitest'

// ---- Extracted pure logic (mirrors ChatInputBox.vue) ----

function isValidMentionAt(text: string, atIndex: number): boolean {
  if (atIndex === 0) return true
  const preceding = text[atIndex - 1]
  return preceding === ' ' || preceding === '\n'
}

function findMentionAtIndex(text: string): number {
  let idx = text.lastIndexOf('@')
  while (idx >= 0) {
    if (isValidMentionAt(text, idx)) return idx
    idx = text.lastIndexOf('@', idx - 1)
  }
  return -1
}

function shouldSendOnEnter(e: { key: string; shiftKey: boolean; isComposing: boolean }): boolean {
  return e.key === 'Enter' && !e.shiftKey && !e.isComposing
}

// ---- Tests ----

describe('findMentionAtIndex', () => {
  it('detects @ at start of text', () => {
    expect(findMentionAtIndex('@skill')).toBe(0)
  })

  it('detects @ after a space', () => {
    expect(findMentionAtIndex('hello @skill')).toBe(6)
  })

  it('detects @ after a newline', () => {
    expect(findMentionAtIndex('hello\n@skill')).toBe(6)
  })

  it('does NOT trigger on email address', () => {
    expect(findMentionAtIndex('user@gmail.com')).toBe(-1)
  })

  it('does NOT trigger when @ is mid-word', () => {
    expect(findMentionAtIndex('abc@def')).toBe(-1)
  })

  it('returns -1 when no @ present', () => {
    expect(findMentionAtIndex('hello world')).toBe(-1)
  })

  it('returns valid @ when mixed with invalid ones', () => {
    // "email@test.com @skill" — only the second @ after space is valid
    const text = 'email@test.com @skill'
    const idx = findMentionAtIndex(text)
    expect(idx).toBe(15)
  })

  it('returns -1 for empty string', () => {
    expect(findMentionAtIndex('')).toBe(-1)
  })

  it('handles single @ at end of text', () => {
    expect(findMentionAtIndex('@')).toBe(0)
  })

  it('handles @ preceded by newline at beginning', () => {
    expect(findMentionAtIndex('\n@skill')).toBe(1)
  })
})

describe('shouldSendOnEnter (IME guard)', () => {
  it('returns true for plain Enter', () => {
    expect(shouldSendOnEnter({ key: 'Enter', shiftKey: false, isComposing: false })).toBe(true)
  })

  it('returns false when Shift+Enter (newline)', () => {
    expect(shouldSendOnEnter({ key: 'Enter', shiftKey: true, isComposing: false })).toBe(false)
  })

  it('returns false when isComposing (IME active — e.g. Chinese input)', () => {
    expect(shouldSendOnEnter({ key: 'Enter', shiftKey: false, isComposing: true })).toBe(false)
  })

  it('returns false for non-Enter key', () => {
    expect(shouldSendOnEnter({ key: 'a', shiftKey: false, isComposing: false })).toBe(false)
  })

  it('returns false when both shiftKey and isComposing', () => {
    expect(shouldSendOnEnter({ key: 'Enter', shiftKey: true, isComposing: true })).toBe(false)
  })
})
