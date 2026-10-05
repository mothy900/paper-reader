import { useRef } from 'react'
import { useBlocks, usePapers, useUploadPaper } from '../lib/queries'
import { useReader } from '../store'

export function LeftSidebar() {
  const paperId = useReader((s) => s.paperId)
  const openPaper = useReader((s) => s.openPaper)
  const { data: papers = [] } = usePapers()
  const upload = useUploadPaper()
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = (file: File | undefined) => {
    if (!file) return
    upload.mutate(file, { onSuccess: (paper) => openPaper(paper.id) })
  }

  return (
    <aside className="sidebar">
      <section>
        <h2 className="section-label">라이브러리</h2>
        <button
          type="button"
          className="upload"
          onClick={() => inputRef.current?.click()}
          disabled={upload.isPending}
        >
          {upload.isPending ? '분석 중…' : 'PDF 열기'}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          hidden
          onChange={(e) => {
            handleFile(e.target.files?.[0])
            e.target.value = ''
          }}
        />
        {upload.error && <p className="error">{upload.error.message}</p>}
        <ul className="paper-list">
          {papers.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                className={p.id === paperId ? 'is-active' : ''}
                onClick={() => openPaper(p.id)}
              >
                <span className="paper-title">{p.title}</span>
                <span className="paper-meta">
                  {p.status === 'failed' ? '분석 실패' : `${p.page_count}쪽`}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      {paperId && <Outline paperId={paperId} />}
    </aside>
  )
}

function Outline({ paperId }: { paperId: string }) {
  const { data: blocks = [] } = useBlocks(paperId)
  const scrollToBlock = useReader((s) => s.scrollToBlock)
  const headings = blocks.filter((b) => b.type === 'heading')

  return (
    <section>
      <h2 className="section-label">목차</h2>
      {headings.length === 0 ? (
        <p className="muted">감지된 제목이 없습니다.</p>
      ) : (
        <ul className="outline">
          {headings.map((h) => (
            <li key={h.id}>
              <button type="button" onClick={() => scrollToBlock(h.id)}>
                {h.text}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
