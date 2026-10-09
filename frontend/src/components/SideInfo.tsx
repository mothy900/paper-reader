import type { Scope, SideTab } from '../store'
import { useReader } from '../store'
import { ExplainPanel } from './ExplainPanel'
import { FocusView } from './FocusView'
import { TranslatePanel } from './TranslatePanel'

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
        {sideTab === 'explain' && (
          <>
            <FocusView />
            <ExplainPanel />
          </>
        )}
        {sideTab === 'translation' && <TranslatePanel />}
        {(sideTab === 'mentions' || sideTab === 'qa') && <p className="muted">다음 단계에서 연결됩니다.</p>}
      </div>
    </aside>
  )
}
