import { findAbstractBlocks } from '../lib/abstract'
import { sentencesInRanges } from '../lib/focus'
import { useExplain } from '../lib/llm'
import { useBlocks, usePapers } from '../lib/queries'
import { useReader } from '../store'
import { ReadingPrep } from './PrepCards'

/** 준비 탭: 읽기 전 준비 카드와 읽는 방법 안내. 논문을 열면 처음 보이는 화면. */
export function StartGuide({ paperId }: { paperId: string }) {
  const { data: blocks = [] } = useBlocks(paperId)
  const { data: papers } = usePapers()
  const paper = papers?.find((p) => p.id === paperId)
  const setFocus = useReader((s) => s.setFocus)
  const scrollToBlock = useReader((s) => s.scrollToBlock)
  const run = useExplain((s) => s.run)
  const abstract = findAbstractBlocks(blocks, paper?.abstract ?? null)

  const explainAbstract = () => {
    const ranges = abstract.map((b) => ({ blockId: b.id, start: 0, end: b.text.length }))
    const focus = {
      source: 'block' as const,
      text: abstract.map((b) => b.text).join(' '),
      blockIds: abstract.map((b) => b.id),
      ranges,
      sentenceIds: sentencesInRanges(ranges, blocks),
    }
    setFocus(focus)
    scrollToBlock(abstract[0].id)
    run(paperId, focus, 'basic')
  }

  return (
    <div className="start-guide">
      <ReadingPrep paperId={paperId} />
      <h2>이 논문 읽기 시작하기</h2>
      {abstract.length > 0 && (
        <section className="start-step">
          <h3>1. 초록으로 전체 그림 잡기</h3>
          <p className="muted">초록은 논문 전체를 한 문단으로 줄인 글이에요. 먼저 읽으면 나머지가 쉬워져요.</p>
          <button type="button" className="primary" onClick={explainAbstract}>
            초록 해설 보기
          </button>
        </section>
      )}
      <section className="start-step">
        <h3>{abstract.length > 0 ? '2' : '1'}. 막히는 곳에서 바로 묻기</h3>
        <ul className="start-tips">
          <li>
            <strong>문장</strong>을 드래그하면 번역과 쉬운 설명이 바로 나와요
          </li>
          <li>
            모르는 <strong>단어</strong>는 더블클릭
          </li>
          <li>
            <strong>수식</strong>은 클릭한 뒤 "이 부분 해설 보기"
          </li>
          <li>
            문단 전체를 옮기려면 <strong>번역</strong> 탭에서 문단을 클릭
          </li>
        </ul>
      </section>
      <p className="start-note muted">해설 한 번에 약 0.3~0.4¢, 같은 해설을 다시 보면 무료예요.</p>
    </div>
  )
}
