import { describe, expect, it } from 'vitest'
import cases from '../../../shared/normalize_cases.json'
import { normalize } from './normalize'

describe('normalize (shared cases with backend)', () => {
  it.each(cases)('$name', ({ input, expected }) => {
    expect(normalize(input)).toBe(expected)
  })
})
