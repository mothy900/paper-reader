import { useMemo, useState } from 'react'
import type { Block } from '../lib/api'
import type { Mention, MentionGroups, Term } from '../lib/glossary'
import { sentenceAround } from '../lib/glossary'
import { useMentions } from '../lib/mentions'
import { useBlocks } from '../lib/queries'
import { useReader } from '../store'
import { RichText } from './RichText'

/** 한 번에 보여주는 개수. 지금 보는 곳에 가까운 것부터. */
const PAGE = 5

export function MentionsPanel() {
  const focus = useReader((s) => s.focus)
  const paperId = useReader((s) => s.paperId)
  const setMentionTerm = useReader((s) => s.setMentionTerm)
  const { data: blocks = [] } = useBlocks(paperId)
  const view = useMentions()
  const byId = useMemo(() => new Map(blocks.map((b) => [b.id, b])), [blocks])

  if (!focus) {
    return (
      <p className="muted mentions-hint">
        본문에서 용어를 드래그하거나 문단을 클릭하면, 그 용어가 논문의 어디에 또 나오는지 보여 드려요. 처음 정의한
        문장은 맨 위에 고정돼요.
      </p>
    )
  }
  if (!view) return <p className="muted">용어집을 불러오는 중…</p>

  const { candidates, term, query, groups } = view
  return (
    <div className="mentions">
      {candidates.length > 1 && (
        <div className="term-chips" role="group" aria-label="이 부분의 용어">
          {candidates.map((t) => (
            <button
              key={t.key}
              type="button"
              aria-pressed={t === term}
              onClick={() => setMentionTerm(t.key)}
              title={t.long ?? undefined}
            >
              {t.label} <span className="muted">{t.occurrences.length}</span>
            </button>
          ))}
        </div>
      )}
      {term && (
        <header className="term-head">
          <strong>{term.label}</strong>
          {term.long && <span> = {term.long}</span>}
          <span className="muted"> · 논문 전체 {term.occurrences.length}번</span>
        </header>
      )}
      {query && groups && (
        <header className="term-head">
          <strong>“{query}”</strong>
          <span className="muted"> · 본문 {groups.total}곳</span>
          <p className="muted">용어집에 없는 말이라 글자 그대로 찾았어요.</p>
        </header>
      )}
      {!groups && (
        <p className="muted">
          {focus.source === 'block'
            ? '이 문단에는 용어집에 있는 용어가 없어요. 궁금한 단어를 드래그해 보세요.'
            : '긴 문장은 관련 언급을 찾지 않아요. 단어나 짧은 구를 드래그해 보세요.'}
        </p>
      )}
      {groups && <MentionGroupsView groups={groups} term={term} byId={byId} />}
    </div>
  )
}

function MentionGroupsView({ groups, term, byId }: { groups: MentionGroups; term: Term | null; byId: Map<string, Block> }) {
  const [moreAbove, setMoreAbove] = useState(false)
  const [moreBelow, setMoreBelow] = useState(false)
  const { pinned, above, below } = groups
  if (!pinned && above.length === 0 && below.length === 0) return <p className="muted">다른 곳에는 나오지 않아요.</p>

  // 정의 문장은 문장 전체가 범위라, 그 안의 용어 등장을 강조한다
  const pinnedMark =
    pinned && pinned.isDefinition
      ? (term?.occurrences
          .map(([blockId, start, end]) => ({ blockId, start, end }))
          .find((m) => m.blockId === pinned.mention.blockId && m.start >= pinned.mention.start && m.end <= pinned.mention.end) ?? {
          ...pinned.mention,
          end: pinned.mention.start,
        })
      : pinned?.mention
  const shownAbove = moreAbove ? above : above.slice(-PAGE)
  const shownBelow = moreBelow ? below : below.slice(0, PAGE)

  return (
    <>
      {pinned && pinnedMark && (
        <section className="mentions-group">
          <h3 className="section-label">{pinned.isDefinition ? '논문의 정의' : '처음 나온 곳'}</h3>
          <MentionItem mention={pinnedMark} byId={byId} pinned />
        </section>
      )}
      {above.length > 0 && (
        <section className="mentions-group">
          <h3 className="section-label">앞쪽 {above.length}</h3>
          {above.length > shownAbove.length && (
            <button type="button" className="link-button" onClick={() => setMoreAbove(true)}>
              {above.length - shownAbove.length}곳 더 보기
            </button>
          )}
          <ul>
            {shownAbove.map((m) => (
              <li key={`${m.blockId}:${m.start}`}>
                <MentionItem mention={m} byId={byId} />
              </li>
            ))}
          </ul>
        </section>
      )}
      <div className="mentions-here" aria-hidden>
        지금 보는 곳
      </div>
      {below.length > 0 && (
        <section className="mentions-group">
          <h3 className="section-label">뒤쪽 {below.length}</h3>
          <ul>
            {shownBelow.map((m) => (
              <li key={`${m.blockId}:${m.start}`}>
                <MentionItem mention={m} byId={byId} />
              </li>
            ))}
          </ul>
          {below.length > shownBelow.length && (
            <button type="button" className="link-button" onClick={() => setMoreBelow(true)}>
              {below.length - shownBelow.length}곳 더 보기
            </button>
          )}
        </section>
      )}
    </>
  )
}

function MentionItem({ mention, byId, pinned }: { mention: Mention; byId: Map<string, Block>; pinned?: boolean }) {
  const flashBlock = useReader((s) => s.flashBlock)
  const block = byId.get(mention.blockId)
  if (!block) return null
  const section = block.section_id ? byId.get(block.section_id) : undefined
  const { start, end, clippedStart, clippedEnd } = sentenceAround(block, mention)
  return (
    <button
      type="button"
      className={`mention${pinned ? ' is-pinned' : ''}`}
      onClick={() => flashBlock(block.id)}
      title="본문에서 보기"
    >
      <span className="paper-meta">
        {block.page}쪽{section ? ` · ${section.text}` : ''}
      </span>
      <span className="mention-text">
        {clippedStart && '…'}
        <RichText text={block.text} start={start} end={end} mark={mention} />
        {clippedEnd && '…'}
      </span>
    </button>
  )
}
