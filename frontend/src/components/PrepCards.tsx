import { useEffect, useState } from 'react'
import { formatCost, modelLabel } from '../lib/llm'
import type { ConceptsResult, DataResult, Evidence, PrepState } from '../lib/prep'
import { DATA_FIELD_LABELS, STATUS_LABELS, usePrep } from '../lib/prep'
import { useBlocks, useStoredPrep } from '../lib/queries'
import { useReader } from '../store'
import { RichText } from './RichText'

const EST_COST = '약 7¢'

/** 읽기 전 준비: 데이터 뼈대 + 사전지식 카드. 버튼을 눌러야 만든다 (덮을 논문엔 비용 없음). */
export function ReadingPrep({ paperId }: { paperId: string }) {
  const stored = useStoredPrep(paperId)
  const prep = usePrep()
  const load = usePrep((s) => s.load)

  useEffect(() => {
    if (stored.data) load(paperId, stored.data)
  }, [paperId, stored.data, load])

  const started = prep.paperId === paperId && (prep.concepts.status !== 'idle' || prep.data.status !== 'idle')
  const runBoth = () => {
    if (prep.data.status !== 'done') prep.run(paperId, 'data')
    if (prep.concepts.status !== 'done') prep.run(paperId, 'concepts')
  }

  return (
    <section className="prep">
      <h2>읽기 전 준비</h2>
      {!started ? (
        <>
          <p className="muted">
            이 논문의 데이터가 무엇이고 어떻게 검증했는지(데이터 뼈대), 읽기 전에 알아 둘 개념(사전지식)을 정리해요.
          </p>
          <button type="button" className="primary" onClick={runBoth} disabled={stored.isLoading}>
            읽기 전 준비 만들기 <span className="muted">({EST_COST})</span>
          </button>
        </>
      ) : (
        <>
          <DataCard paperId={paperId} state={prep.data} onRetry={() => prep.run(paperId, 'data')} />
          <ConceptsCard state={prep.concepts} onRetry={() => prep.run(paperId, 'concepts')} />
        </>
      )}
    </section>
  )
}

function CardStatus({ state, label, onRetry }: { state: PrepState<unknown>; label: string; onRetry: () => void }) {
  if (state.status === 'streaming') {
    return (
      <p className="muted">
        {label} 정리하는 중…{state.progress ? ` (${state.progress.toLocaleString()}자)` : ' 논문을 읽고 있어요'}
      </p>
    )
  }
  if (state.status === 'error' || state.status === 'refused') {
    return (
      <p className="error">
        {state.message}{' '}
        <button type="button" className="link" onClick={onRetry}>
          다시 시도
        </button>
      </p>
    )
  }
  if (state.status === 'idle') {
    return (
      <button type="button" className="link" onClick={onRetry}>
        {label} 만들기
      </button>
    )
  }
  return null
}

function CardMeta({ state }: { state: PrepState<unknown> }) {
  if (state.status !== 'done') return null
  return (
    <p className="explain-meta">
      {[modelLabel(state.model), state.cached ? '저장된 결과' : formatCost(state.costUsd ?? 0)].filter(Boolean).join(' · ')}
    </p>
  )
}

function DataCard({ paperId, state, onRetry }: { paperId: string; state: PrepState<DataResult>; onRetry: () => void }) {
  const { data: blocks = [] } = useBlocks(paperId)
  const r = state.result
  return (
    <div className="prep-card">
      <h3>데이터 뼈대</h3>
      {state.scope && (
        <p className="prep-scope muted">
          읽은 범위: {state.scope}
          {state.tables && state.tables.length > 0 && ` · 표 ${state.tables.length}개 포함`}
        </p>
      )}
      <CardStatus state={state} label="데이터 뼈대" onRetry={onRetry} />
      {r && !r.applicable && <p>이 논문은 다루는 데이터가 없어요: {r.not_applicable_reason}</p>}
      {r && r.applicable && (
        <>
          <dl className="skeleton">
            {DATA_FIELD_LABELS.map(([key, label]) => {
              const f = r.fields[key]
              if (!f) return null
              return (
                <div key={key} className="skeleton-row">
                  <dt>{label}</dt>
                  <dd>
                    <span className={`status status-${f.status}`}>{STATUS_LABELS[f.status]}</span>
                    <span className="skeleton-value">
                      <Rich text={f.value} />
                    </span>
                    {f.status === 'inferred' && f.calculation && (
                      <span className="skeleton-calc muted">계산: {f.calculation}</span>
                    )}
                    {f.numbers_unverified?.length > 0 && (
                      <span className="skeleton-calc muted">
                        근거에서 확인되지 않은 숫자: {f.numbers_unverified.join(', ')}
                      </span>
                    )}
                    <EvidenceChips evidence={f.evidence} />
                  </dd>
                </div>
              )
            })}
          </dl>
          {r.supplementary?.length > 0 && (
            <p className="prep-note muted">
              보충 자료에 더 있을 수 있어요:{' '}
              {r.supplementary.map((s) => (
                <JumpChip key={s.block_id} blockId={s.block_id} label={pageOf(blocks, s.block_id)} title={s.snippet} />
              ))}
            </p>
          )}
          {r.warnings.length > 0 && (
            <>
              <h4>주의해서 볼 점</h4>
              <ul className="prep-list">
                {r.warnings.map((w, i) => (
                  <li key={i}>
                    <Rich text={w.text} /> <EvidenceChips evidence={w.evidence} />
                  </li>
                ))}
              </ul>
            </>
          )}
          {r.questions.length > 0 && (
            <>
              <h4>
                의뢰받는다면 먼저 물어볼 것 <CopyButton text={r.questions.map((q) => `- ${q}`).join('\n')} />
              </h4>
              <ul className="prep-list">
                {r.questions.map((q, i) => (
                  <li key={i}>
                    <Rich text={q} />
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
      <CardMeta state={state} />
    </div>
  )
}

function ConceptsCard({ state, onRetry }: { state: PrepState<ConceptsResult>; onRetry: () => void }) {
  return (
    <div className="prep-card">
      <h3>알아 두면 좋은 개념</h3>
      <CardStatus state={state} label="사전지식" onRetry={onRetry} />
      {state.result && (
        <ol className="concepts">
          {state.result.concepts.map((c, i) => (
            <li key={i}>
              <strong>
                <Rich text={c.name} />
              </strong>
              {c.original && (
                <span className="muted">
                  {' '}
                  (<Rich text={c.original} />)
                </span>
              )}
              <p>
                <Rich text={c.what} />
              </p>
              <p className="muted">
                <Rich text={c.why} /> {c.section_ref && <JumpChip blockId={c.section_ref} label="나오는 곳" />}
              </p>
            </li>
          ))}
        </ol>
      )}
      <CardMeta state={state} />
    </div>
  )
}

function Rich({ text }: { text: string }) {
  return <RichText text={text} start={0} end={text.length} mark={null} />
}

const CHECK_LABEL: Record<Evidence['check'], string> = {
  verified: '원문 확인',
  image: '표 이미지',
  unverified: '근거 미확인',
}

function EvidenceChips({ evidence }: { evidence: Evidence[] }) {
  if (evidence.length === 0) return null
  return (
    <span className="chips">
      {evidence.map((e, i) =>
        e.block_id ? (
          <JumpChip
            key={i}
            blockId={e.block_id}
            label={`근거 ${i + 1}`}
            title={`${CHECK_LABEL[e.check]} · "${e.quote}"`}
            check={e.check}
          />
        ) : (
          <span key={i} className="chip chip-unverified" title={`"${e.quote}" — 위치를 찾지 못했어요`}>
            근거 {i + 1}?
          </span>
        ),
      )}
    </span>
  )
}

function JumpChip({
  blockId,
  label,
  title,
  check,
}: {
  blockId: string
  label: string
  title?: string
  check?: Evidence['check']
}) {
  const flashBlock = useReader((s) => s.flashBlock)
  return (
    <button type="button" className={`chip${check ? ` chip-${check}` : ''}`} title={title} onClick={() => flashBlock(blockId)}>
      {label}
    </button>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      className="link"
      onClick={() => {
        void navigator.clipboard.writeText(text).then(() => {
          setCopied(true)
          setTimeout(() => setCopied(false), 1500)
        })
      }}
    >
      {copied ? '복사됨' : '복사'}
    </button>
  )
}

function pageOf(blocks: { id: string; page: number }[], blockId: string): string {
  const b = blocks.find((x) => x.id === blockId)
  return b ? `${b.page}쪽` : '위치'
}
