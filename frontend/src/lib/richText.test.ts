import { describe, expect, it } from 'vitest'
import { richPieces } from './richText'

const t = 'SG = W_{st} - W_{s0} and R^{2}.'

describe('richPieces', () => {
  it('turns markup into sub/sup pieces', () => {
    expect(richPieces(t, 0, t.length, null)).toEqual([
      { text: 'SG = W', kind: 'normal', marked: false },
      { text: 'st', kind: 'sub', marked: false },
      { text: ' - W', kind: 'normal', marked: false },
      { text: 's0', kind: 'sub', marked: false },
      { text: ' and R', kind: 'normal', marked: false },
      { text: '2', kind: 'sup', marked: false },
      { text: '.', kind: 'normal', marked: false },
    ])
  })

  it('splits normal text at mark boundaries and marks whole script pieces', () => {
    const start = t.indexOf('W_{st}')
    const pieces = richPieces(t, 0, t.indexOf(' and'), { start: 3, end: start + 3 })
    expect(pieces).toEqual([
      { text: 'SG ', kind: 'normal', marked: false },
      { text: '= W', kind: 'normal', marked: true },
      { text: 'st', kind: 'sub', marked: true },
      { text: ' - W', kind: 'normal', marked: false },
      { text: 's0', kind: 'sub', marked: false },
    ])
  })

  it('handles text without markup', () => {
    expect(richPieces('plain text', 0, 5, null)).toEqual([{ text: 'plain', kind: 'normal', marked: false }])
  })
})
