import { useEffect, useState } from 'react'
import type { Block } from '../lib/api'
import { renderRegion } from '../lib/pdf'
import { useBlocks } from '../lib/queries'
import { useReader } from '../store'
import { RichText } from './RichText'


/** 포커스한 문장들 (드래그한 부분 강조). 수식은 원본 이미지로. */
export function FocusView() {
  const paperId = useReader((s) => s.paperId)
  const focus = useReader((s) => s.focus)
  const scrollToBlock = useReader((s) => s.scrollToBlock)
  const { data: blocks = [] } = useBlocks(paperId)

  if (!focus) {
    return paperId ? <NoFocusHint /> : null
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
            {(block.type === 'equation' || block.type === 'table') && paperId ? (
              <RegionImage key={block.id} paperId={paperId} block={block} />
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

/** 이미지를 새 탭에서 연다 (data: 주소는 브라우저가 새 탭 열기를 막아 blob 주소로 바꾼다) */
function openImage(dataUrl: string) {
  void fetch(dataUrl)
    .then((r) => r.blob())
    .then((blob) => window.open(URL.createObjectURL(blob), '_blank', 'noopener'))
}

function NoFocusHint() {
  const setSideTab = useReader((s) => s.setSideTab)
  return (
    <p className="muted">
      본문에서 문장을 드래그하거나 단어를 더블클릭하면 여기에 해설이 나와요. 처음이라면{' '}
      <button type="button" className="link" onClick={() => setSideTab('prep')}>
        준비 탭
      </button>
      에서 시작해 보세요.
    </p>
  )
}

/**
 * 수식·표는 PDF에서 텍스트로 되살리기 어려워(분수·첨자·셀 배치가 사라진다) 원본 영역을 이미지로 보여준다.
 * 추출된 텍스트는 접어서 함께 둔다.
 */
function RegionImage({ paperId, block }: { paperId: string; block: Block }) {
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
        <>
          <img src={src} alt={block.text} />
          <button type="button" className="link region-open" onClick={() => openImage(src)}>
            크게 보기
          </button>
        </>
      ) : (
        <p className="muted">{failed ? '이미지를 그리지 못했습니다.' : '불러오는 중…'}</p>
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

