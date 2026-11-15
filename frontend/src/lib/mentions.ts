import { useMemo } from 'react'
import { useReader } from '../store'
import type { MentionGroups, Term } from './glossary'
import { SEARCH_MAX_WORDS, groupMentions, searchText, termsForFocus } from './glossary'
import { useBlocks, useGlossary } from './queries'

export interface MentionsView {
  /** 포커스에 걸린 용어들 (여럿이면 고를 수 있다) */
  candidates: Term[]
  term: Term | null
  /** 용어집에 없어 본문을 글자 그대로 찾은 말 */
  query: string | null
  groups: MentionGroups | null
}

/** 포커스의 관련 언급. 로컬 계산이라 탭을 보고 있지 않아도 항상 계산한다 (탭의 개수 표시). */
export function useMentions(): MentionsView | null {
  const paperId = useReader((s) => s.paperId)
  const focus = useReader((s) => s.focus)
  const mentionTerm = useReader((s) => s.mentionTerm)
  const { data: blocks } = useBlocks(paperId)
  const { data: terms } = useGlossary(paperId)

  return useMemo(() => {
    if (!focus || !blocks || !terms) return null
    const candidates = termsForFocus(terms, focus)
    const term = candidates.find((t) => t.key === mentionTerm) ?? candidates[0] ?? null
    if (term) {
      return { candidates, term, query: null, groups: groupMentions(term.occurrences, term.definition, focus, blocks) }
    }
    const words = focus.text.trim().split(/\s+/).length
    if (focus.source === 'selection' && words <= SEARCH_MAX_WORDS) {
      const found = searchText(blocks, focus.text)
      return { candidates, term: null, query: focus.text.trim(), groups: groupMentions(found, null, focus, blocks) }
    }
    return { candidates, term: null, query: null, groups: null }
  }, [focus, blocks, terms, mentionTerm])
}

