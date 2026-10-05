import { usePapers } from '../lib/queries'
import { useReader } from '../store'

export function Header() {
  const paperId = useReader((s) => s.paperId)
  const zoom = useReader((s) => s.zoom)
  const setZoom = useReader((s) => s.setZoom)
  const showBlocks = useReader((s) => s.showBlocks)
  const toggleShowBlocks = useReader((s) => s.toggleShowBlocks)
  const { data: papers } = usePapers()
  const paper = papers?.find((p) => p.id === paperId)

  return (
    <header className="header">
      <span className="brand">Reader</span>
      <span className="header-title" title={paper?.title}>
        {paper?.title ?? ''}
      </span>
      {paper && paper.hidden_text_count > 0 && (
        <span
          className="header-notice"
          title="흰 글씨·아주 작은 글씨처럼 사람 눈에 보이지 않는 텍스트입니다. AI를 조작하려는 문구일 수 있어 해설·번역에서 제외했습니다."
        >
          숨은 텍스트 {paper.hidden_text_count}곳을 제외했습니다
        </span>
      )}
      {paper?.language === 'ko' && (
        <span className="header-notice">한국어 논문은 아직 일부 기능만 지원합니다</span>
      )}
      {paper && (
        <div className="header-tools">
          <label className="toggle">
            <input type="checkbox" checked={showBlocks} onChange={toggleShowBlocks} />
            블록 경계
          </label>
          <button type="button" onClick={() => setZoom(zoom - 0.1)} aria-label="축소">
            −
          </button>
          <span className="zoom">{Math.round(zoom * 100)}%</span>
          <button type="button" onClick={() => setZoom(zoom + 0.1)} aria-label="확대">
            +
          </button>
        </div>
      )}
    </header>
  )
}
