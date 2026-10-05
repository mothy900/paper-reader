import type { Block } from './api'
import { normalize } from './normalize'
import type { PageRect } from './selection'

/** 블록 텍스트(정규화됨) 안의 범위 */
export interface BlockRange {
  blockId: string
  start: number
  end: number
}

/** 문장 id: "{blockId}:{idx}" — 출처 표기 [s:p3-12:2]와 같은 형식 */
export const sentenceId = (blockId: string, idx: number) => `${blockId}:${idx}`

/**
 * 비교용 느슨한 형태: 영숫자만 남기고 소문자로.
 * pdf.js와 PyMuPDF는 줄끝 하이픈·공백·구두점을 다르게 뽑아서 정확히 일치하지 않는 경우가 많다.
 * map[i]는 느슨한 문자열의 i번째 문자가 원문에서 몇 번째 문자인지.
 */
function loosen(text: string): { loose: string; map: number[] } {
  let loose = ''
  const map: number[] = []
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (/[\p{L}\p{N}]/u.test(ch)) {
      loose += ch.toLowerCase()
      map.push(i)
    }
  }
  return { loose, map }
}

function allIndexesOf(haystack: string, needle: string): number[] {
  const out: number[] = []
  for (let i = haystack.indexOf(needle); i !== -1; i = haystack.indexOf(needle, i + 1)) out.push(i)
  return out
}

/**
 * 드래그한 텍스트가 블록들의 어디에 해당하는지 찾는다.
 *
 * @param blocks 선택 영역과 겹친 블록 (읽기 순서)
 * @param firstRect 선택의 첫 사각형. 같은 문구가 블록 안에 여러 번 나올 때 위치로 고른다.
 * @returns 블록별 범위. 못 찾으면 블록 전체를 범위로 돌려준다.
 */
export function locateSelection(text: string, blocks: Block[], firstRect?: PageRect): BlockRange[] {
  if (blocks.length === 0) return []
  const whole = () => blocks.map((b) => ({ blockId: b.id, start: 0, end: b.text.length }))

  // 블록들을 한 줄로 이어 붙이고, 이어 붙인 위치 → (블록, 오프셋) 변환표를 만든다
  const joined = blocks.map((b) => b.text).join(' ')
  const owner: { block: Block; offset: number }[] = []
  for (const b of blocks) {
    for (let i = 0; i < b.text.length; i++) owner.push({ block: b, offset: i })
    owner.push({ block: b, offset: b.text.length }) // 구분 공백
  }

  const hay = loosen(joined)
  const needle = loosen(normalize(text)).loose
  if (!needle) return whole()

  let candidates = allIndexesOf(hay.loose, needle)
  let needleLen = needle.length
  if (candidates.length === 0 && needle.length > 40) {
    // 중간이 어긋나도 앞뒤 20자로 찾는다 (수식·특수문자가 섞인 선택)
    const head = allIndexesOf(hay.loose, needle.slice(0, 20))
    const tail = needle.slice(-20)
    candidates = head.filter((h) => hay.loose.indexOf(tail, h) !== -1)
    if (candidates.length > 0) {
      needleLen = hay.loose.indexOf(tail, candidates[0]) + 20 - candidates[0]
    }
  }
  if (candidates.length === 0) return whole()

  const startLoose = pickCandidate(candidates, hay.loose.length, blocks[0], firstRect)
  const startJoined = hay.map[startLoose]
  const endJoined = hay.map[startLoose + needleLen - 1] + 1
  return splitByBlock(owner, startJoined, endJoined)
}

/** 후보가 여럿이면 선택의 화면 위치와 가장 가까운 것을 고른다 */
function pickCandidate(candidates: number[], total: number, first: Block, rect?: PageRect): number {
  if (candidates.length === 1 || !rect) return candidates[0]
  const [x0, y0, x1, y1] = first.bbox
  const lineHeight = Math.max(rect.y1 - rect.y0, 1)
  const lines = Math.max(Math.round((y1 - y0) / lineHeight), 1)
  const line = Math.min(Math.floor((rect.y0 - y0) / lineHeight), lines - 1)
  const xFrac = Math.min(Math.max((rect.x0 - x0) / Math.max(x1 - x0, 1), 0), 1)
  const expected = ((line + xFrac) / lines) * total
  return candidates.reduce((best, c) => (Math.abs(c - expected) < Math.abs(best - expected) ? c : best))
}

function splitByBlock(owner: { block: Block; offset: number }[], start: number, end: number): BlockRange[] {
  const ranges: BlockRange[] = []
  for (let i = start; i < end; i++) {
    const { block, offset } = owner[i]
    const last = ranges.at(-1)
    if (last?.blockId === block.id) last.end = Math.min(offset + 1, block.text.length)
    else ranges.push({ blockId: block.id, start: offset, end: Math.min(offset + 1, block.text.length) })
  }
  return ranges.filter((r) => r.end > r.start)
}

/** 범위와 겹치는 문장 id (블록 순서, 문장 순서) */
export function sentencesInRanges(ranges: BlockRange[], blocks: Block[]): string[] {
  const byId = new Map(blocks.map((b) => [b.id, b]))
  return ranges.flatMap(({ blockId, start, end }) => {
    const block = byId.get(blockId)
    if (!block) return []
    return block.sentences.flatMap(([s, e], idx) => (s < end && e > start ? [sentenceId(blockId, idx)] : []))
  })
}

/** 클릭 지점(PDF 좌표)에 있는 블록. 그림 블록은 제외한다. */
export function blockAtPoint(blocks: Block[], page: number, x: number, y: number): Block | undefined {
  return blocks.find((b) => {
    if (b.page !== page || b.type === 'figure') return false
    const [x0, y0, x1, y1] = b.bbox
    return x >= x0 && x <= x1 && y >= y0 && y <= y1
  })
}
