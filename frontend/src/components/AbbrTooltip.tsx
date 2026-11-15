import { useEffect, useMemo, useState } from 'react'
import type { Term } from '../lib/glossary'
import { abbreviationMap } from '../lib/glossary'
import { useGlossary } from '../lib/queries'
import { useReader } from '../store'

interface Tip {
  term: Term
  left: number
  top: number
}

/**
 * 약어에 마우스를 올리면 풀네임을 보여준다. data-abbr-scope가 붙은 곳(본문·해설 패널)에서만.
 * 드래그 중(버튼을 누른 채)에는 띄우지 않는다. 설정에서 끌 수 있다.
 */
export function AbbrTooltip() {
  const paperId = useReader((s) => s.paperId)
  const enabled = useReader((s) => s.abbrTooltip)
  const { data: terms } = useGlossary(paperId)
  const map = useMemo(() => abbreviationMap(terms ?? []), [terms])
  const [tip, setTip] = useState<Tip | null>(null)

  useEffect(() => {
    if (!enabled || map.size === 0) return
    let frame = 0
    let last: MouseEvent | null = null

    const check = () => {
      frame = 0
      const e = last
      if (!e) return
      const inScope = e.target instanceof Element && e.target.closest('[data-abbr-scope]')
      const hit = e.buttons === 0 && inScope ? wordAt(e.clientX, e.clientY) : null
      const term = hit ? map.get(hit.word) : undefined
      setTip((prev) => {
        if (!term || !hit) return null
        const next = { term, left: hit.rect.left, top: hit.rect.bottom + 4 }
        return prev && prev.term === term && prev.left === next.left && prev.top === next.top ? prev : next
      })
    }
    const onMove = (e: MouseEvent) => {
      last = e
      if (!frame) frame = requestAnimationFrame(check)
    }
    const hide = () => setTip(null)
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mousedown', hide)
    document.addEventListener('scroll', hide, true)
    return () => {
      cancelAnimationFrame(frame)
      setTip(null)
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mousedown', hide)
      document.removeEventListener('scroll', hide, true)
    }
  }, [enabled, map])

  if (!tip || !enabled) return null
  return (
    <div className="abbr-tip" role="tooltip" style={{ left: tip.left, top: tip.top }}>
      <strong>{tip.term.short}</strong> {tip.term.long}
    </div>
  )
}

const WORD_CHAR = /[A-Za-z0-9]/

/** 화면 좌표 아래의 영문·숫자 단어와 그 위치. 글자 위가 아니면 null. */
function wordAt(x: number, y: number): { word: string; rect: DOMRect } | null {
  let node: Node | null = null
  let offset = 0
  if (document.caretPositionFromPoint) {
    const pos = document.caretPositionFromPoint(x, y)
    node = pos?.offsetNode ?? null
    offset = pos?.offset ?? 0
  } else if (document.caretRangeFromPoint) {
    const range = document.caretRangeFromPoint(x, y)
    node = range?.startContainer ?? null
    offset = range?.startOffset ?? 0
  }
  if (!(node instanceof Text)) return null
  const text = node.data
  let start = offset
  let end = offset
  while (start > 0 && WORD_CHAR.test(text[start - 1])) start--
  while (end < text.length && WORD_CHAR.test(text[end])) end++
  if (end - start < 2) return null
  const range = document.createRange()
  range.setStart(node, start)
  range.setEnd(node, end)
  const rect = range.getBoundingClientRect()
  // 캐럿 API는 글자 밖을 가리켜도 가장 가까운 글자를 돌려주므로, 실제로 단어 위인지 확인한다
  if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) return null
  return { word: text.slice(start, end), rect }
}
