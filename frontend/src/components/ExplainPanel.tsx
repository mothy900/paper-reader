import type { LlmState } from '../lib/llm'
import { fromApiFocus, formatCost, modelLabel, useExplain } from '../lib/llm'
import { useHistory } from '../lib/queries'
import { useReader } from '../store'
import { RichText } from './RichText'
import { SectionText } from './SectionText'

/** 작업별 섹션 순서와 제목 (서버 tasks.py의 sections와 같은 이름) */
const SECTION_LABELS: Record<string, [string, string][]> = {
  explain_sentence: [
    ['translation', '번역'],
    ['explanation', '쉬운 설명'],
    ['role', '논문에서의 역할'],
    ['terms', '핵심 용어'],
  ],
  explain_word: [
    ['in_paper', '이 논문에서의 의미'],
    ['general', '일반적인 의미'],
    ['plain', '쉽게 말하면'],
  ],
  explain_table: [
    ['summary', '이 표가 보여주는 것'],
    ['how_to_read', '읽는 법'],
    ['key_points', '눈여겨볼 점'],
  ],
  explain_equation: [
    ['meaning', '이 식이 말하는 것'],
    ['symbols', '기호'],
    ['intuition', '직관적으로'],
  ],
}

export function ExplainPanel() {
  const paperId = useReader((s) => s.paperId)
  const focus = useReader((s) => s.focus)
  const explain = useExplain()

  if (!paperId) return null
  return (
    <div className="explain">
      {focus && explain.status === 'idle' && (
        <button type="button" className="primary" onClick={() => explain.run(paperId, focus, 'basic')}>
          {focus.source === 'block' ? '이 부분 해설 보기' : '해설 보기'}
        </button>
      )}
      {explain.status !== 'idle' && <ExplainResult state={explain} />}
      {focus && (explain.status === 'done' || explain.status === 'error') && (
        <div className="explain-actions">
          {explain.detail === 'basic' ? (
            <button type="button" onClick={() => explain.run(paperId, focus, 'deep')}>
              더 자세히 <span className="muted">Sonnet</span>
            </button>
          ) : (
            <button type="button" onClick={() => explain.run(paperId, focus, 'basic')}>
              짧은 해설로
            </button>
          )}
        </div>
      )}
      <History paperId={paperId} />
    </div>
  )
}

function ExplainResult({ state }: { state: LlmState }) {
  const labels = SECTION_LABELS[state.task ?? ''] ?? []
  const waiting = state.status === 'streaming' && Object.keys(state.sections).length === 0
  return (
    <section className="explain-result" aria-live="polite">
      {waiting && <p className="muted">해설을 쓰는 중…</p>}
      {labels.map(([name, label]) =>
        state.sections[name] ? (
          <div key={name} className="explain-section">
            <h3 className="section-label">{label}</h3>
            <SectionText text={state.sections[name]} />
          </div>
        ) : null,
      )}
      {(state.status === 'refused' || state.status === 'error') && <p className="error">{state.message}</p>}
      {state.status === 'done' && (
        <p className="explain-meta">
          {modelLabel(state.model)} · {state.cached ? '저장된 해설' : formatCost(state.costUsd ?? 0)}
          {state.truncated && ' · 길이 제한으로 잘렸어요'}
        </p>
      )}
    </section>
  )
}

function History({ paperId }: { paperId: string }) {
  const { data: items = [] } = useHistory(paperId)
  const reopen = useReader((s) => s.reopenExplain)
  if (items.length === 0) return null
  return (
    <details className="history">
      <summary>해설 기록 {items.length}</summary>
      <ul>
        {items.map((h) => (
          <li key={h.id}>
            <button type="button" onClick={() => reopen(fromApiFocus(h.focus), h.detail)}>
              <RichText text={h.label} start={0} end={h.label.length} mark={null} />
              {h.detail === 'deep' && <span className="muted"> · 자세히</span>}
            </button>
          </li>
        ))}
      </ul>
    </details>
  )
}
