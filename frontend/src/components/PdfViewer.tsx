import * as pdfjs from 'pdfjs-dist'
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { Block } from '../lib/api'
import { api } from '../lib/api'
import { useBlocks } from '../lib/queries'
import { blocksForRects, selectionToPageRects } from '../lib/selection'
import { useReader } from '../store'

pdfjs.GlobalWorkerOptions.workerSrc = workerSrc

interface PageSize {
  width: number
  height: number
}

export function PdfViewer({ paperId }: { paperId: string }) {
  const zoom = useReader((s) => s.zoom)
  const scrollTarget = useReader((s) => s.scrollTarget)
  const setSelection = useReader((s) => s.setSelection)
  const { data: blocks = [] } = useBlocks(paperId)
  const [doc, setDoc] = useState<pdfjs.PDFDocumentProxy | null>(null)
  const [sizes, setSizes] = useState<PageSize[]>([])
  const [error, setError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const task = pdfjs.getDocument({ url: api.fileUrl(paperId) })
    let cancelled = false
    task.promise
      .then(async (pdf) => {
        const pages = await Promise.all(
          Array.from({ length: pdf.numPages }, (_, i) => pdf.getPage(i + 1)),
        )
        if (cancelled) return
        setSizes(pages.map((p) => p.getViewport({ scale: 1 })))
        setDoc(pdf)
      })
      .catch((e: unknown) => !cancelled && setError(String(e)))
    return () => {
      cancelled = true
      setDoc(null)
      setSizes([])
      setError(null)
      void task.destroy()
    }
  }, [paperId])

  const blocksByPage = useMemo(() => {
    const map = new Map<number, Block[]>()
    for (const b of blocks) map.set(b.page, [...(map.get(b.page) ?? []), b])
    return map
  }, [blocks])

  useEffect(() => {
    if (!scrollTarget || !scrollRef.current) return
    const block = blocks.find((b) => b.id === scrollTarget.blockId)
    const pageEl = scrollRef.current.querySelector<HTMLElement>(`[data-page="${block?.page}"]`)
    if (!block || !pageEl) return
    scrollRef.current.scrollTo({ top: pageEl.offsetTop + block.bbox[1] * zoom - 24, behavior: 'smooth' })
  }, [scrollTarget, blocks, zoom])

  const handleMouseUp = () => {
    const sel = window.getSelection()
    const text = sel?.toString().trim() ?? ''
    if (!sel || sel.rangeCount === 0 || !text || !scrollRef.current) return
    const pageEls = [...scrollRef.current.querySelectorAll<HTMLElement>('[data-page]')]
    const rects = selectionToPageRects(sel.getRangeAt(0), pageEls, zoom)
    setSelection({ text, blockIds: blocksForRects(rects, blocks) })
  }

  if (error) return <div className="viewer-message">PDF를 열 수 없습니다: {error}</div>
  if (!doc) return <div className="viewer-message">불러오는 중…</div>

  return (
    <div className="viewer" ref={scrollRef} onMouseUp={handleMouseUp}>
      {sizes.map((size, i) => (
        <PdfPage
          key={i + 1}
          doc={doc}
          pageNumber={i + 1}
          size={size}
          scale={zoom}
          blocks={blocksByPage.get(i + 1) ?? []}
          root={scrollRef}
        />
      ))}
    </div>
  )
}

interface PdfPageProps {
  doc: pdfjs.PDFDocumentProxy
  pageNumber: number
  size: PageSize
  scale: number
  blocks: Block[]
  root: React.RefObject<HTMLDivElement | null>
}

function PdfPage({ doc, pageNumber, size, scale, blocks, root }: PdfPageProps) {
  const ref = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const textRef = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)
  const showBlocks = useReader((s) => s.showBlocks)
  const selectedIds = useReader((s) => s.selection?.blockIds)

  // 화면 근처에 온 페이지만 렌더링한다
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(([entry]) => entry.isIntersecting && setVisible(true), {
      root: root.current,
      rootMargin: '800px 0px',
    })
    io.observe(el)
    return () => io.disconnect()
  }, [root])

  useEffect(() => {
    if (!visible) return
    let cancelled = false
    let renderTask: pdfjs.RenderTask | null = null
    let textLayer: pdfjs.TextLayer | null = null

    void doc.getPage(pageNumber).then(async (page) => {
      const canvas = canvasRef.current
      const textEl = textRef.current
      if (cancelled || !canvas || !textEl) return
      const viewport = page.getViewport({ scale })
      const dpr = window.devicePixelRatio || 1
      canvas.width = Math.floor(viewport.width * dpr)
      canvas.height = Math.floor(viewport.height * dpr)
      renderTask = page.render({
        canvas,
        viewport,
        transform: dpr === 1 ? undefined : [dpr, 0, 0, dpr, 0, 0],
      })
      textEl.replaceChildren()
      textLayer = new pdfjs.TextLayer({
        textContentSource: page.streamTextContent(),
        container: textEl,
        viewport,
      })
      await Promise.all([renderTask.promise, textLayer.render()]).catch((e: unknown) => {
        if (!(e instanceof pdfjs.RenderingCancelledException)) throw e
      })
    })

    return () => {
      cancelled = true
      renderTask?.cancel()
      textLayer?.cancel()
    }
  }, [doc, pageNumber, scale, visible])

  return (
    <div
      ref={ref}
      className="pdf-page"
      data-page={pageNumber}
      style={
        {
          width: size.width * scale,
          height: size.height * scale,
          '--total-scale-factor': scale,
        } as React.CSSProperties
      }
    >
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%' }} />
      <div className="block-layer">
        {blocks.map((b) => {
          const selected = selectedIds?.includes(b.id)
          if (!showBlocks && !selected) return null
          const [x0, y0, x1, y1] = b.bbox
          return (
            <div
              key={b.id}
              className={`block-box${selected ? ' is-selected' : ''}`}
              data-type={b.type}
              style={{ left: x0 * scale, top: y0 * scale, width: (x1 - x0) * scale, height: (y1 - y0) * scale }}
            >
              {showBlocks && <span className="block-label">{b.id}</span>}
            </div>
          )
        })}
      </div>
      <div ref={textRef} className="textLayer" />
    </div>
  )
}
