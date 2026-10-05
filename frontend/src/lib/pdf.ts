import * as pdfjs from 'pdfjs-dist'
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { api } from './api'

pdfjs.GlobalWorkerOptions.workerSrc = workerSrc

const MAX_OPEN = 2
const docs = new Map<string, pdfjs.PDFDocumentLoadingTask>()

/** 논문 PDF를 연다. 뷰어와 수식 이미지가 같은 문서 객체를 쓰도록 최근 문서 몇 개를 캐시한다. */
export function loadPdf(paperId: string): Promise<pdfjs.PDFDocumentProxy> {
  const cached = docs.get(paperId)
  if (cached) {
    docs.delete(paperId)
    docs.set(paperId, cached) // 최근 사용 순서로
    return cached.promise
  }
  const task = pdfjs.getDocument({ url: api.fileUrl(paperId) })
  task.promise.catch(() => docs.delete(paperId))
  docs.set(paperId, task)
  while (docs.size > MAX_OPEN) {
    const [oldest, oldTask] = docs.entries().next().value!
    docs.delete(oldest)
    void oldTask.destroy()
  }
  return task.promise
}

/**
 * 페이지의 일부 영역(PDF 좌표)을 이미지로 그린다. 수식처럼 텍스트로 되살리기 어려운 부분에 쓴다.
 * 3단계에서는 같은 이미지를 LLM에 보낸다.
 */
export async function renderRegion(
  paperId: string,
  pageNumber: number,
  bbox: [number, number, number, number],
  scale = 2.5,
  padding = 4,
): Promise<string> {
  const doc = await loadPdf(paperId)
  const page = await doc.getPage(pageNumber)
  const [x0, y0, x1, y1] = [bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding]
  const viewport = page.getViewport({ scale, offsetX: -x0 * scale, offsetY: -y0 * scale })
  const canvas = document.createElement('canvas')
  canvas.width = Math.ceil((x1 - x0) * scale)
  canvas.height = Math.ceil((y1 - y0) * scale)
  await page.render({ canvas, viewport }).promise
  return canvas.toDataURL('image/png')
}
