import { describe, expect, it } from 'vitest'
import type { Block } from './api'
import type { Term } from './glossary'
import { abbreviationMap, groupMentions, matchTerm, searchText, termKey, termsForFocus } from './glossary'
import type { Focus } from '../store'

const llm: Term = {
  key: 'large language model',
  label: 'LLM',
  kind: 'abbr',
  short: 'LLM',
  long: 'large language model',
  definition: ['b1', 0, 40],
  occurrences: [
    ['b1', 10, 30],
    ['b2', 4, 7],
    ['b3', 0, 3],
    ['b4', 5, 8],
  ],
}
const rate: Term = { key: 'learning rate', label: 'learning rate', kind: 'key', short: null, long: null, definition: null, occurrences: [['b3', 10, 23], ['b4', 20, 33]] }
const terms = [llm, rate]

function block(id: string, seq: number, text: string, type: Block['type'] = 'paragraph'): Block {
  return { id, seq, page: 1, type, text, bbox: [0, 0, 1, 1], section_id: null, level: null, sentences: [[0, text.length]] }
}
const blocks = [block('b1', 1, 'x'.repeat(40)), block('b2', 2, 'The LLM is big.'), block('b3', 3, 'LLM with a learning rate.'), block('b4', 4, 'Then LLMs use learning rates.')]

function focus(source: Focus['source'], text: string, blockId: string, start: number, end: number): Focus {
  return { source, text, blockIds: [blockId], ranges: [{ blockId, start, end }], sentenceIds: [] }
}

describe('glossary', () => {
  it('matches terms like the server', () => {
    expect(termKey('Neural  Networks')).toBe('neural network')
    expect(matchTerm(terms, 'LLMs')).toBe(llm)
    expect(matchTerm(terms, '(LLM),')).toBe(llm)
    expect(matchTerm(terms, 'Large language models')).toBe(llm)
    expect(matchTerm(terms, 'llm')).toBeNull()
    expect(matchTerm(terms, 'Learning Rates')).toBe(rate)
  })

  it('picks the dragged term, otherwise terms inside the focus', () => {
    expect(termsForFocus(terms, focus('selection', 'LLM', 'b2', 4, 7))).toEqual([llm])
    expect(termsForFocus(terms, focus('block', '', 'b3', 0, 25))).toEqual([llm, rate])
    expect(termsForFocus(terms, focus('selection', 'something else', 'b2', 0, 3))).toEqual([])
  })

  it('pins the definition and splits the rest around the focus', () => {
    const g = groupMentions(llm.occurrences, llm.definition, focus('selection', 'LLM', 'b3', 0, 3), blocks)
    expect(g.pinned).toEqual({ mention: { blockId: 'b1', start: 0, end: 40 }, isDefinition: true })
    expect(g.above).toEqual([{ blockId: 'b2', start: 4, end: 7 }]) // b1 안의 등장은 정의 문장이라 빠진다
    expect(g.below).toEqual([{ blockId: 'b4', start: 5, end: 8 }]) // 포커스 자신(b3)은 빠진다
    expect(g.total).toBe(4)
  })

  it('pins the first occurrence when there is no definition', () => {
    const g = groupMentions(rate.occurrences, null, focus('block', '', 'b1', 0, 40), blocks)
    expect(g.pinned?.isDefinition).toBe(false)
    expect(g.above).toEqual([])
    expect(g.below).toEqual([{ blockId: 'b4', start: 20, end: 33 }])
  })

  it('lists a sentence once even if the term appears twice in it', () => {
    const twice: Term = { ...rate, occurrences: [['b4', 5, 8], ['b4', 20, 33]] }
    const g = groupMentions(twice.occurrences, null, focus('block', '', 'b1', 0, 40), blocks)
    expect(g.below).toEqual([])
    expect(g.pinned?.mention).toEqual({ blockId: 'b4', start: 5, end: 8 })
    const both = groupMentions([['b4', 5, 8], ['b4', 20, 33]], ['b1', 0, 40], focus('block', '', 'b1', 0, 40), blocks)
    expect(both.below).toEqual([{ blockId: 'b4', start: 5, end: 8 }])
  })

  it('searches plain text on word boundaries', () => {
    expect(searchText(blocks, 'learning rate')).toEqual([['b3', 11, 24]])
    expect(searchText(blocks, 'LL')).toEqual([])
  })

  it('maps abbreviations and their plurals', () => {
    const map = abbreviationMap(terms)
    expect(map.get('LLMs')).toBe(llm)
    expect(map.has('learning rate')).toBe(false)
  })
})
