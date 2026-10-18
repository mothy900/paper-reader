import type { Block } from './api'

/**
 * 초록에 해당하는 블록. 파서가 뽑은 초록 텍스트와 겹치는 문단을 찾고,
 * 초록이 arXiv 메타데이터에서 왔거나 못 찾으면 "Abstract" 제목 바로 다음 문단을 쓴다.
 */
export function findAbstractBlocks(blocks: Block[], abstract: string | null): Block[] {
  const paragraphs = blocks.filter((b) => b.type === 'paragraph')
  if (abstract) {
    const hits = paragraphs.filter((b) => b.text.length > 40 && abstract.includes(b.text.slice(0, 60)))
    if (hits.length > 0) return hits
  }
  const heading = blocks.findIndex((b) => b.type === 'heading' && /^abstract\b/i.test(b.text.trim()))
  if (heading === -1) return []
  const next = blocks.slice(heading + 1).find((b) => b.type === 'paragraph')
  return next ? [next] : []
}
