/**
 * 용어집과 관련 언급 (LLM 없음). 용어집과 등장 위치는 서버(app/text/glossary.py)가 만든다.
 * 여기서는 포커스에 맞는 용어를 고르고, 등장 위치를 포커스 위/아래로 나눈다.
 */
import type { Block } from './api'
import type { Focus } from '../store'

/** [block_id, start, end] */
export type Span = [string, number, number]

export interface Term {
  key: string
  label: string
  kind: 'abbr' | 'named' | 'key'
  short: string | null
  long: string | null
  /** 논문이 정의한 문장 (약어·이름 붙인 용어만) */
  definition: Span | null
  occurrences: Span[]
}

export interface Mention {
  blockId: string
  start: number
  end: number
}

export interface MentionGroups {
  /** 정의한 문장, 정의가 없으면 처음 나온 곳 */
  pinned: { mention: Mention; isDefinition: boolean } | null
  above: Mention[]
  below: Mention[]
  total: number
}

// --- 서버의 term_key와 같은 규칙 (대소문자·복수형·공백 차이를 없앤 비교용 키) ---

function singular(word: string): string {
  const low = word.toLowerCase()
  if (low.length > 4 && low.endsWith('ies')) return word.slice(0, -3) + 'y'
  if (low.length > 4 && /(sses|ches|shes|xes)$/.test(low)) return word.slice(0, -2)
  if (low.length > 3 && low.endsWith('s') && !/(ss|us|is)$/.test(low)) return word.slice(0, -1)
  return word
}

export function termKey(phrase: string): string {
  const words = phrase.toLowerCase().split(/\s+/).filter(Boolean)
  if (words.length === 0) return ''
  words[words.length - 1] = singular(words[words.length - 1])
  return words.join(' ')
}

const TRIM = /^[\s.,;:()[\]"']+|[\s.,;:()[\]"']+$/g

/** 드래그한 말이 어느 용어인지. 약어는 대소문자까지 같아야 한다 ("IT"와 "it"). */
export function matchTerm(terms: Term[], text: string): Term | null {
  const t = text.replace(TRIM, '')
  if (!t) return null
  const abbr = terms.find((x) => x.kind === 'abbr' && (t === x.short || t === `${x.short}s`))
  if (abbr) return abbr
  const key = termKey(t)
  return terms.find((x) => x.key === key) ?? null
}

/**
 * 포커스에서 관련 언급을 볼 용어 후보.
 * - 드래그한 말 자체가 용어면 그 용어 하나
 * - 아니면 포커스 범위 안에 등장하는 용어들 (나온 순서)
 */
export function termsForFocus(terms: Term[], focus: Focus): Term[] {
  if (focus.source === 'selection') {
    const exact = matchTerm(terms, focus.text)
    if (exact) return [exact]
  }
  const hits: { term: Term; order: number }[] = []
  for (const term of terms) {
    let order = Infinity
    for (const [blockId, s, e] of term.occurrences) {
      const idx = focus.ranges.findIndex((r) => r.blockId === blockId && s < r.end && e > r.start)
      if (idx !== -1) order = Math.min(order, idx * 1e6 + s)
    }
    if (order !== Infinity) hits.push({ term, order })
  }
  return hits.sort((a, b) => a.order - b.order).map((h) => h.term)
}

/** 등장 위치를 포커스 기준 위/아래로 나누고, 정의(없으면 처음 나온 곳)를 맨 위에 고정한다. */
export function groupMentions(occurrences: Span[], definition: Span | null, focus: Focus, blocks: Block[]): MentionGroups {
  const seq = new Map(blocks.map((b) => [b.id, b.seq]))
  const anchor = focus.ranges[0]
  const anchorPos: [number, number] = [seq.get(anchor?.blockId) ?? 0, anchor?.start ?? 0]
  const inFocus = (m: Mention) => focus.ranges.some((r) => r.blockId === m.blockId && m.start < r.end && m.end > r.start)
  const before = (m: Mention) => {
    const s = seq.get(m.blockId) ?? 0
    return s < anchorPos[0] || (s === anchorPos[0] && m.start < anchorPos[1])
  }

  const all = occurrences.map(([blockId, start, end]) => ({ blockId, start, end }))
  const pinnedSpan = definition ?? occurrences[0] ?? null
  const pinned = pinnedSpan
    ? { mention: { blockId: pinnedSpan[0], start: pinnedSpan[1], end: pinnedSpan[2] }, isDefinition: definition !== null }
    : null
  // 고정한 곳(정의 문장, 또는 처음 나온 곳)과 포커스 안의 등장은 목록에서 뺀다
  const atPinned = (m: Mention) =>
    pinned !== null && m.blockId === pinned.mention.blockId && m.start >= pinned.mention.start && m.end <= pinned.mention.end
  // 한 문장에 여러 번 나오면 한 번만 보여준다
  const byId = new Map(blocks.map((b) => [b.id, b]))
  const sentenceKey = (m: Mention) =>
    `${m.blockId}:${byId.get(m.blockId)?.sentences.findIndex(([s, e]) => s <= m.start && m.start < e) ?? -1}`
  const seen = new Set<string>(pinned ? [sentenceKey(pinned.mention)] : [])
  const list = all.filter((m) => {
    if (inFocus(m) || atPinned(m)) return false
    const key = sentenceKey(m)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
  return {
    pinned,
    above: list.filter(before),
    below: list.filter((m) => !before(m)),
    total: all.length,
  }
}

const SEARCH_TYPES = new Set(['paragraph', 'caption', 'heading'])
const MAX_SEARCH = 300

function escapeRegExp(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** 용어집에 없는 말은 본문에서 그대로 찾는다 (단어 경계, 대소문자 무시). */
export function searchText(blocks: Block[], text: string): Span[] {
  const needle = text.replace(TRIM, '').replace(/\s+/g, ' ')
  if (needle.length < 2) return []
  const re = new RegExp(`(?<![A-Za-z0-9])${escapeRegExp(needle)}(?![A-Za-z0-9])`, 'gi')
  const out: Span[] = []
  for (const b of blocks) {
    if (!SEARCH_TYPES.has(b.type)) continue
    for (const m of b.text.matchAll(re)) {
      out.push([b.id, m.index, m.index + m[0].length])
      if (out.length >= MAX_SEARCH) return out
    }
  }
  return out
}

/** 짧은 말(단어·구)만 본문 검색한다. 문장을 통째로 찾는 건 의미가 없다. */
export const SEARCH_MAX_WORDS = 4

/** 약어 → 용어 (본문 위에서 마우스를 올렸을 때 풀이용). 복수형("LLMs")도 찾는다. */
export function abbreviationMap(terms: Term[]): Map<string, Term> {
  const map = new Map<string, Term>()
  for (const t of terms) {
    if (t.kind === 'abbr' && t.short) {
      map.set(t.short, t)
      map.set(`${t.short}s`, t)
    }
  }
  return map
}

/** 등장한 문장 (길면 등장 위치 주변만) */
export function sentenceAround(
  block: Block,
  m: Mention,
  maxChars = 220,
): { start: number; end: number; clippedStart: boolean; clippedEnd: boolean } {
  const sentence = block.sentences.find(([s, e]) => s <= m.start && m.start < e) ?? [0, block.text.length]
  let [start, end] = sentence
  if (end - start > maxChars) {
    const half = Math.floor((maxChars - (m.end - m.start)) / 2)
    start = Math.max(start, m.start - half)
    end = Math.min(end, m.end + half)
    // 단어 중간에서 자르지 않는다
    const sp = block.text.indexOf(' ', start)
    if (start > sentence[0] && sp !== -1 && sp < m.start) start = sp + 1
    const ep = block.text.lastIndexOf(' ', end)
    if (end < sentence[1] && ep > m.end) end = ep
  }
  return { start, end, clippedStart: start > sentence[0], clippedEnd: end < sentence[1] }
}
