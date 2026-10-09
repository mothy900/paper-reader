import { useRef, useState } from 'react'
import type { Paper, UploadResult } from '../lib/api'
import { formatAddedAt } from '../lib/format'
import { useBlocks, useImportPaper, usePapers, useUploadPaper } from '../lib/queries'
import { useReader } from '../store'

export function LeftSidebar() {
  const paperId = useReader((s) => s.paperId)
  const openPaper = useReader((s) => s.openPaper)
  const { data: papers = [] } = usePapers()
  const upload = useUploadPaper()
  const importer = useImportPaper()
  const inputRef = useRef<HTMLInputElement>(null)
  const [url, setUrl] = useState('')
  const [notice, setNotice] = useState<string | null>(null)
  const busy = upload.isPending || importer.isPending
  const error = upload.error ?? importer.error

  const opened = ({ paper, existed }: UploadResult) => {
    openPaper(paper.id)
    if (existed) setNotice('이미 있는 논문이라 기존 논문을 열었어요.')
  }

  const handleFile = (file: File | undefined) => {
    if (!file) return
    setNotice(null)
    importer.reset()
    upload.mutate(file, { onSuccess: opened })
  }

  const handleImport = (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return
    setNotice(null)
    upload.reset()
    importer.mutate(url.trim(), {
      onSuccess: (result) => {
        setUrl('')
        opened(result)
      },
    })
  }

  return (
    <aside className="sidebar">
      <section>
        <h2 className="section-label">라이브러리</h2>
        <form className="import" onSubmit={handleImport}>
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="주소, arXiv ID, DOI"
            aria-label="논문 주소, arXiv ID 또는 DOI"
            disabled={busy}
          />
          <button type="submit" disabled={busy || !url.trim()}>
            {importer.isPending ? '가져오는 중…' : '가져오기'}
          </button>
        </form>
        <button
          type="button"
          className="upload"
          onClick={() => inputRef.current?.click()}
          disabled={busy}
        >
          {upload.isPending ? '분석 중…' : 'PDF 파일 열기'}
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
        {error && <p className="error notice">{error.message}</p>}
        {notice && <p className="muted notice">{notice}</p>}
        <ul className="paper-list">
          {papers.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                className={p.id === paperId ? 'is-active' : ''}
                onClick={() => openPaper(p.id)}
              >
                <span className="paper-title">{p.title}</span>
                <span className="paper-meta">{paperMeta(p)}</span>
                <span className="paper-meta" title={new Date(p.created_at).toLocaleString('ko-KR')}>
                  {formatAddedAt(p.created_at)} 추가
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

function paperMeta(p: Paper): string {
  if (p.status === 'failed') return '분석 실패'
  const author = p.authors.length === 0 ? null : p.authors.length === 1 ? p.authors[0] : `${p.authors[0]} 외`
  return [author, p.year, `${p.page_count}쪽`].filter(Boolean).join(' · ')
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
            <li key={h.id} data-level={h.level ?? 1}>
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
