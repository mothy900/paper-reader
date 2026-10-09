import { describe, expect, it } from 'vitest'
import { formatAddedAt } from './format'

describe('formatAddedAt', () => {
  const now = new Date(2026, 9, 9, 15, 0) // 2026-10-09 15:00 (로컬)

  it('shows time for today', () => {
    expect(formatAddedAt(new Date(2026, 9, 9, 9, 5).toISOString(), now)).toBe('오늘 09:05')
  })

  it('shows month and day within this year', () => {
    expect(formatAddedAt(new Date(2026, 9, 6, 12, 0).toISOString(), now)).toBe('10월 6일')
  })

  it('shows the full date for earlier years', () => {
    expect(formatAddedAt(new Date(2025, 2, 2).toISOString(), now)).toBe('2025. 3. 2.')
  })

  it('returns empty text for invalid input', () => {
    expect(formatAddedAt('not a date', now)).toBe('')
  })
})
