import type { SideTab } from '../store'
import { useReader } from '../store'
import { ExplainPanel } from './ExplainPanel'
import { FocusView } from './FocusView'
import { useMentions } from '../lib/mentions'
import { MentionsPanel } from './MentionsPanel'
import { StartGuide } from './StartGuide'
import { TranslatePanel } from './TranslatePanel'

// ready: false인 탭은 아직 기능이 없어 누를 수 없게 보여준다 (동작하지 않는 버튼을 누르게 하지 않는다)
const TABS: { id: SideTab; label: string; ready: boolean }[] = [
  { id: 'prep', label: '준비', ready: true },
  { id: 'explain', label: '해설', ready: true },
  { id: 'translation', label: '번역', ready: true },
  { id: 'mentions', label: '관련 언급', ready: true },
  { id: 'qa', label: 'Q&A', ready: false },
]

export function SideInfo() {
  const sideTab = useReader((s) => s.sideTab)
  const setSideTab = useReader((s) => s.setSideTab)
  const paperId = useReader((s) => s.paperId)
  // 관련 언급은 탭을 보고 있지 않아도 계산해 개수를 보여준다 (로컬 계산이라 비용이 없다)
  const mentionCount = useMentions()?.groups?.total ?? 0

  return (
    <aside className="side-info">
      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={sideTab === t.id}
            disabled={!t.ready}
            title={t.ready ? undefined : '다음 단계에서 추가돼요'}
            onClick={() => setSideTab(t.id)}
          >
            {t.label}
            {t.id === 'mentions' && mentionCount > 0 && <span className="tab-count">{mentionCount}</span>}
            {!t.ready && <span className="tab-soon">준비 중</span>}
          </button>
        ))}
      </nav>
      <div className="side-body" data-abbr-scope>
        {sideTab === 'prep' && paperId && <StartGuide paperId={paperId} />}
        {sideTab === 'explain' && (
          <>
            <FocusView />
            <ExplainPanel />
          </>
        )}
        {sideTab === 'translation' && <TranslatePanel />}
        {sideTab === 'mentions' && <MentionsPanel />}
      </div>
    </aside>
  )
}
