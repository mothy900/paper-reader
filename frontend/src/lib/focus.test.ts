import { describe, expect, it } from 'vitest'
import type { Block } from './api'
import { blockAtPoint, locateSelection, sentencesInRanges } from './focus'

function block(id: string, text: string, sentences: [number, number][], bbox = [0, 0, 200, 40]): Block {
  return {
    id,
    seq: Number(id.split('-')[1]),
    page: 1,
    type: 'paragraph',
    text,
    bbox: bbox as Block['bbox'],
    section_id: null,
    level: null,
    sentences,
  }
}

const A = block('p1-1', 'Self-attention is cheap. It scales well. We use it.', [
  [0, 24],
  [25, 40],
  [41, 51],
])
const B = block('p1-2', 'Residual connections help. They ease training.', [
  [0, 26],
  [27, 47],
])

const text = (b: Block, r: { start: number; end: number }) => b.text.slice(r.start, r.end)

describe('locateSelection', () => {
  it('finds an exact phrase inside one block', () => {
    const [r] = locateSelection('It scales well', [A])
    expect(text(A, r)).toBe('It scales well')
    expect(sentencesInRanges([r], [A])).toEqual(['p1-1:1'])
  })

  it('tolerates line-break hyphenation and extra whitespace from pdf.js', () => {
    const [r] = locateSelection('Self-\nattention  is cheap', [A])
    expect(text(A, r)).toBe('Self-attention is cheap')
  })

  it('tolerates ligatures and curly quotes', () => {
    const b = block('p1-3', 'An efficient "fine" model.', [[0, 26]])
    const [r] = locateSelection('e\ufb03cient \u201c\ufb01ne\u201d', [b])
    expect(text(b, r)).toBe('efficient "fine')
  })

  it('splits a selection that spans two blocks', () => {
    const ranges = locateSelection('We use it. Residual connections', [A, B])
    expect(ranges.map((r) => r.blockId)).toEqual(['p1-1', 'p1-2'])
    expect(text(A, ranges[0])).toBe('We use it.')
    expect(text(B, ranges[1])).toBe('Residual connections')
    expect(sentencesInRanges(ranges, [A, B])).toEqual(['p1-1:2', 'p1-2:0'])
  })

  it('picks the occurrence closest to where the user dragged', () => {
    // 두 줄짜리 블록. "it"은 1번째 줄 앞쪽(It scales)과 2번째 줄 끝(use it)에 있다
    const rect = { page: 1, x0: 180, y0: 21, x1: 190, y1: 39 }
    const [r] = locateSelection('it', [A], rect)
    expect(r.start).toBe(A.text.lastIndexOf('it'))
  })

  it('falls back to whole blocks when the text is not found', () => {
    expect(locateSelection('nothing like this', [A])).toEqual([{ blockId: 'p1-1', start: 0, end: A.text.length }])
  })
})

describe('blockAtPoint', () => {
  it('returns the block under the point and ignores figures', () => {
    const fig = { ...block('p1-9', '56-layer', [], [0, 0, 500, 500]), type: 'figure' as const }
    expect(blockAtPoint([fig, A], 1, 10, 10)?.id).toBe('p1-1')
    expect(blockAtPoint([fig, A], 1, 300, 300)).toBeUndefined()
    expect(blockAtPoint([A], 2, 10, 10)).toBeUndefined()
  })
})
