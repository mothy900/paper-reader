import { formatCost, modelLabel, useTranslations } from '../lib/llm'
import { useBlocks } from '../lib/queries'
import { useReader } from '../store'
import { RichText } from './RichText'
import { SectionText } from './SectionText'

/** 포커스한 문단을 원문과 번역으로 나란히. 번역은 버튼을 눌렀을 때만 (토큰 절약). */
export function TranslatePanel() {
  const paperId = useReader((s) => s.paperId)
  const focus = useReader((s) => s.focus)
  const { data: blocks = [] } = useBlocks(paperId)
  const byBlock = useTranslations((s) => s.byBlock)
  const run = useTranslations((s) => s.run)

  if (!paperId || !focus) {
    return <p className="muted">번역할 문단을 클릭하거나 드래그하세요.</p>
  }
  const targets = blocks.filter(
    (b) => focus.blockIds.includes(b.id) && !['figure', 'equation', 'table'].includes(b.type),
  )
  if (targets.length === 0) return <p className="muted">이 부분은 번역할 텍스트가 없어요.</p>

  return (
    <div className="translate">
      {targets.map((b) => {
        const t = byBlock[b.id]
        return (
          <section key={b.id} className="translate-block">
            <p className="translate-source">
              <RichText text={b.text} start={0} end={b.text.length} mark={null} />
            </p>
            {!t || t.status === 'idle' ? (
              <button type="button" className="primary" onClick={() => run(paperId, b.id)}>
                번역
              </button>
            ) : (
              <div className="translate-result" aria-live="polite">
                {t.sections.translation ? (
                  <SectionText text={t.sections.translation} />
                ) : (
                  t.status === 'streaming' && <p className="muted">번역하는 중…</p>
                )}
                {(t.status === 'error' || t.status === 'refused') && <p className="error">{t.message}</p>}
                {t.status === 'done' && (
                  <p className="explain-meta">
                    {modelLabel(t.model)} · {t.cached ? '저장된 번역' : formatCost(t.costUsd ?? 0)}
                  </p>
                )}
              </div>
            )}
          </section>
        )
      })}
    </div>
  )
}
