import { describe, expect, it } from 'vitest'
import type { LlmState } from './llm'
import { IDLE, formatCost, fromApiFocus, reduceEvent, toApiFocus } from './llm'

describe('reduceEvent', () => {
  it('accumulates section deltas and finishes with cost', () => {
    let s: LlmState = { ...IDLE, status: 'streaming' }
    s = reduceEvent(s, 'meta', { task: 'explain_word', model: 'claude-haiku-4-5', cached: false })
    s = reduceEvent(s, 'section', { name: 'plain', delta: '쉽게 ' })
    s = reduceEvent(s, 'section', { name: 'plain', delta: '말하면' })
    s = reduceEvent(s, 'done', { model: 'claude-haiku-4-5', cached: false, cost_usd: 0.0021 })
    expect(s).toMatchObject({ status: 'done', task: 'explain_word', sections: { plain: '쉽게 말하면' }, costUsd: 0.0021 })
  })

  it('drops partial sections on refusal', () => {
    let s = reduceEvent({ ...IDLE, status: 'streaming' }, 'section', { name: 'translation', delta: '부분' })
    s = reduceEvent(s, 'refused', { category: 'bio', message: '거절' })
    expect(s).toMatchObject({ status: 'refused', sections: {}, message: '거절' })
  })
})

describe('formatCost', () => {
  it.each([
    [0, '무료'],
    [0.0002, '0.02¢'],
    [0.0042, '0.4¢'],
    [0.123, '12.3¢'],
    [1.5, '$1.50'],
  ])('%s -> %s', (usd, expected) => {
    expect(formatCost(usd)).toBe(expected)
  })
})

describe('focus conversion', () => {
  it('round-trips between store and API shapes', () => {
    const focus = {
      source: 'selection' as const,
      text: 'x',
      blockIds: ['p1-2'],
      ranges: [{ blockId: 'p1-2', start: 0, end: 1 }],
      sentenceIds: ['p1-2:0'],
    }
    expect(toApiFocus(focus).block_ids).toEqual(['p1-2'])
    expect(fromApiFocus(toApiFocus(focus))).toEqual(focus)
  })
})
