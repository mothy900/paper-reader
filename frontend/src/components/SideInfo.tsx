import { useBlocks } from '../lib/queries'
import type { Scope, SideTab } from '../store'
import { useReader } from '../store'

const TABS: { id: SideTab; label: string }[] = [
  { id: 'translation', label: '번역' },
  { id: 'explain', label: '해설' },
  { id: 'mentions', label: '관련 언급' },
  { id: 'qa', label: 'Q&A' },
]

const SCOPES: { id: Scope; label: string }[] = [
  { id: 'paper', label: '전체' },
  { id: 'section', label: '섹션' },
  { id: 'paragraph', label: '문단' },
  { id: 'selection', label: '선택' },
]

export function SideInfo() {
  const sideTab = useReader((s) => s.sideTab)
  const setSideTab = useReader((s) => s.setSideTab)
  const scope = useReader((s) => s.scope)
  const setScope = useReader((s) => s.setScope)
  const hasFocus = useReader((s) => s.focus !== null)

  return (
    <aside className="side-info">
      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={sideTab === t.id}
            onClick={() => setSideTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>
      <div className="scope" role="radiogroup" aria-label="범위">
        {SCOPES.map((s) => (
          <button
            key={s.id}
            type="button"
            role="radio"
            aria-checked={scope === s.id}
            disabled={!hasFocus && (s.id === 'paragraph' || s.id === 'section')}
            title={!hasFocus && (s.id === 'paragraph' || s.id === 'section') ? '본문을 클릭하거나 드래그하세요' : undefined}
            onClick={() => setScope(s.id)}
          >
            {s.label}
          </button>
        ))}
      </div>
      <div className="side-body">
        {sideTab === 'explain' ? <FocusView /> : <p className="muted">다음 단계에서 연결됩니다.</p>}
      </div>
    </aside>
  )
}

/** 2단계: 포커스가 어느 블록·문장에 매핑되는지 보여준다. 3단계에서 해설로 바뀐다. */
function FocusView() {
  const paperId = useReader((s) => s.paperId)
  const focus = useReader((s) => s.focus)
  const scrollToBlock = useReader((s) => s.scrollToBlock)
  const { data: blocks = [] } = useBlocks(paperId)

  if (!focus) {
    return <p className="muted">본문에서 문장이나 단어를 드래그하거나, 문단을 클릭해 보세요.</p>
  }

  const byId = new Map(blocks.map((b) => [b.id, b]))
  return (
    <div className="focus">
      {focus.source === 'selection' && <blockquote>{focus.text}</blockquote>}
      {focus.ranges.map((range) => {
        const block = byId.get(range.blockId)
        if (!block) return null
        const section = block.section_id ? byId.get(block.section_id) : undefined
        return (
          <section key={range.blockId} className="focus-block">
            <button type="button" className="paper-meta" onClick={() => scrollToBlock(block.id)}>
              {section ? `${section.text} · ` : ''}
              {block.page}쪽 · {block.id}
            </button>
            <ol className="sentences">
              {block.sentences.map(([s, e], idx) => {
                if (s >= range.end || e <= range.start) return null
                return (
                  <li key={idx}>
                    <SentenceText text={block.text} start={s} end={e} mark={focus.source === 'selection' ? range : null} />
                  </li>
                )
              })}
            </ol>
          </section>
        )
      })}
      {focus.sentenceIds.length === 0 && (
        <p className="error">선택 영역에 해당하는 문장을 찾지 못했습니다.</p>
      )}
    </div>
  )
}

/** 문장을 보여주고, 드래그한 부분은 강조한다 */
function SentenceText({
  text,
  start,
  end,
  mark,
}: {
  text: string
  start: number
  end: number
  mark: { start: number; end: number } | null
}) {
  if (!mark) return <>{text.slice(start, end)}</>
  const ms = Math.max(mark.start, start)
  const me = Math.min(mark.end, end)
  return (
    <>
      {text.slice(start, ms)}
      <mark>{text.slice(ms, me)}</mark>
      {text.slice(me, end)}
    </>
  )
}
