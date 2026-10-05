import { useEffect, useState } from 'react'
import type { Block } from '../lib/api'
import { renderRegion } from '../lib/pdf'
import { useBlocks } from '../lib/queries'
import { richPieces } from '../lib/richText'
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
            {block.type === 'equation' && paperId ? (
              <EquationImage key={block.id} paperId={paperId} block={block} />
            ) : (
              <ol className="sentences">
                {block.sentences.map(([s, e], idx) => {
                  if (s >= range.end || e <= range.start) return null
                  return (
                    <li key={idx}>
                      <RichText
                        text={block.text}
                        start={s}
                        end={e}
                        mark={focus.source === 'selection' ? range : null}
                      />
                    </li>
                  )
                })}
              </ol>
            )}
          </section>
        )
      })}
      {focus.sentenceIds.length === 0 && (
        <p className="error">선택 영역에 해당하는 문장을 찾지 못했습니다.</p>
      )}
    </div>
  )
}

/**
 * 수식은 PDF에서 텍스트로 되살리기 어려워(분수·첨자 배치가 사라진다) 원본 영역을 이미지로 보여준다.
 * 추출된 텍스트는 접어서 함께 둔다.
 */
function EquationImage({ paperId, block }: { paperId: string; block: Block }) {
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    renderRegion(paperId, block.page, block.bbox)
      .then((url) => !cancelled && setSrc(url))
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [paperId, block.page, block.bbox])

  return (
    <figure className="equation">
      {src ? (
        <img src={src} alt={block.text} />
      ) : (
        <p className="muted">{failed ? '수식 이미지를 그리지 못했습니다.' : '수식을 불러오는 중…'}</p>
      )}
      <details>
        <summary>추출된 텍스트</summary>
        <p className="equation-text">
          <RichText text={block.text} start={0} end={block.text.length} mark={null} />
        </p>
      </details>
    </figure>
  )
}

/** 문장을 보여준다. 첨자 표시는 실제 첨자로, 드래그한 부분은 강조로. */
function RichText({
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
  return (
    <>
      {richPieces(text, start, end, mark).map((p, i) => {
        const inner = p.kind === 'sub' ? <sub>{p.text}</sub> : p.kind === 'sup' ? <sup>{p.text}</sup> : p.text
        return p.marked ? <mark key={i}>{inner}</mark> : <span key={i}>{inner}</span>
      })}
    </>
  )
}
