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
