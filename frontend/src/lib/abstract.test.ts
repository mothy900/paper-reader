import { describe, expect, it } from 'vitest'
import type { Block } from './api'
import { findAbstractBlocks } from './abstract'

const block = (id: string, type: Block['type'], text: string): Block => ({
  id,
  seq: Number(id.slice(3)),
  page: 1,
  type,
  text,
  bbox: [0, 0, 1, 1],
  section_id: null,
  level: type === 'heading' ? 1 : null,
  sentences: [[0, text.length]],
})

const P1 = 'Deeper neural networks are more difficult to train. We present a residual learning framework.'
const P2 = 'The depth of representations is of central importance for many visual recognition tasks.'
const blocks = [
  block('p1-1', 'heading', 'Deep Residual Learning'),
  block('p1-2', 'heading', 'Abstract'),
  block('p1-3', 'paragraph', P1),
  block('p1-4', 'paragraph', P2),
  block('p1-5', 'heading', '1. Introduction'),
  block('p1-6', 'paragraph', 'Deep convolutional neural networks have led to a series of breakthroughs.'),
]

describe('findAbstractBlocks', () => {
  it('matches paragraphs contained in the parsed abstract', () => {
    expect(findAbstractBlocks(blocks, `${P1} ${P2}`).map((b) => b.id)).toEqual(['p1-3', 'p1-4'])
  })

  it('falls back to the paragraph after the Abstract heading', () => {
    // arXiv 메타데이터 초록은 PDF 문단과 표기가 달라 직접 일치하지 않을 수 있다
    expect(findAbstractBlocks(blocks, 'A differently worded abstract.').map((b) => b.id)).toEqual(['p1-3'])
    expect(findAbstractBlocks(blocks, null).map((b) => b.id)).toEqual(['p1-3'])
  })

  it('returns nothing when there is no abstract', () => {
    expect(findAbstractBlocks(blocks.slice(4), null)).toEqual([])
  })
})
