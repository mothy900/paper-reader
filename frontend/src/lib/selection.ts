import type { Block } from './api'

/** PDF 좌표(pt)로 변환된 선택 영역 사각형 */
export interface PageRect {
  page: number
  x0: number
  y0: number
  x1: number
  y1: number
}

const TOLERANCE = 2 // pt. 텍스트 레이어 span이 블록 bbox보다 살짝 넘치는 경우 보정

/** 선택 영역과 겹치는 블록 id를 읽기 순서대로 반환한다. */
export function blocksForRects(rects: PageRect[], blocks: Block[]): string[] {
  const hits = blocks.filter((b) =>
    rects.some((r) => {
      if (r.page !== b.page) return false
      const [x0, y0, x1, y1] = b.bbox
      // 사각형 중심이 블록 안에 있으면 그 블록에 속한 것으로 본다.
      // 단순 교차로 판정하면 2단 레이아웃에서 옆 단의 블록까지 잡힌다.
      const cx = (r.x0 + r.x1) / 2
      const cy = (r.y0 + r.y1) / 2
      return (
        cx >= x0 - TOLERANCE && cx <= x1 + TOLERANCE && cy >= y0 - TOLERANCE && cy <= y1 + TOLERANCE
      )
    }),
  )
  return hits.sort((a, b) => a.seq - b.seq).map((b) => b.id)
}

/** 화면의 선택 영역을 페이지별 PDF 좌표로 변환한다. */
export function selectionToPageRects(range: Range, pageElements: HTMLElement[], scale: number): PageRect[] {
  const out: PageRect[] = []
  for (const rect of range.getClientRects()) {
    if (rect.width === 0 || rect.height === 0) continue
    const cx = rect.left + rect.width / 2
    const cy = rect.top + rect.height / 2
    const pageEl = pageElements.find((el) => {
      const p = el.getBoundingClientRect()
      return cx >= p.left && cx <= p.right && cy >= p.top && cy <= p.bottom
    })
    if (!pageEl) continue
    const p = pageEl.getBoundingClientRect()
    out.push({
      page: Number(pageEl.dataset.page),
      x0: (rect.left - p.left) / scale,
      y0: (rect.top - p.top) / scale,
      x1: (rect.right - p.left) / scale,
      y1: (rect.bottom - p.top) / scale,
    })
  }
  return out
}
