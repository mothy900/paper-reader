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
            onClick={() => setScope(s.id)}
          >
            {s.label}
          </button>
        ))}
      </div>
      <div className="side-body">
        {sideTab === 'explain' ? <SelectionDebug /> : <p className="muted">다음 단계에서 연결됩니다.</p>}
      </div>
    </aside>
  )
}

/** 1단계: 드래그한 텍스트가 어느 블록에 매핑되는지 확인하는 용도 */
function SelectionDebug() {
  const paperId = useReader((s) => s.paperId)
  const selection = useReader((s) => s.selection)
  const scrollToBlock = useReader((s) => s.scrollToBlock)
  const { data: blocks = [] } = useBlocks(paperId)

  if (!selection) return <p className="muted">본문에서 문장이나 단어를 드래그해 보세요.</p>

  const matched = blocks.filter((b) => selection.blockIds.includes(b.id))
  return (
    <div className="selection">
      <blockquote>{selection.text}</blockquote>
      <h3 className="section-label">매핑된 블록 {matched.length}개</h3>
      {matched.length === 0 && <p className="error">선택 영역에 해당하는 블록을 찾지 못했습니다.</p>}
      <ul className="matched">
        {matched.map((b) => (
          <li key={b.id}>
            <button type="button" onClick={() => scrollToBlock(b.id)}>
              <span className="paper-meta">
                {b.id} · {b.type} · {b.page}쪽
              </span>
              <span className="matched-text">{b.text}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
