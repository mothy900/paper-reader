export type PaperStatus = 'parsing' | 'ready' | 'failed'
export type BlockType = 'heading' | 'paragraph' | 'caption' | 'figure'

export interface Paper {
  id: string
  title: string
  source_type: string
  source_url: string | null
  authors: string[]
  year: number | null
  arxiv_id: string | null
  doi: string | null
  page_count: number
  language: 'en' | 'ko'
  abstract: string | null
  /** 숨은 텍스트(흰 글씨·초소형 글씨 등)가 발견되어 제외된 곳의 수 */
  hidden_text_count: number
  status: PaperStatus
  error: string | null
  created_at: string
}

export interface Block {
  id: string
  seq: number
  page: number
  type: BlockType
  text: string
  /** PDF 좌표(pt), 페이지 왼쪽 위 원점: [x0, y0, x1, y1] */
  bbox: [number, number, number, number]
  section_id: string | null
  /** heading일 때 1~3 */
  level: number | null
  /** 문장 경계: text.slice(start, end) */
  sentences: [number, number][]
}

export interface UploadResult {
  paper: Paper
  /** 같은 파일이 이미 있어서 기존 논문을 돌려받았는지 */
  existed: boolean
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init)
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail ?? `${res.status} ${res.statusText}`)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

/** 논문을 만드는 요청. 200이면 같은 파일이 이미 있어 기존 논문을 돌려받은 것이다. */
async function createPaper(path: string, init: RequestInit): Promise<UploadResult> {
  const res = await fetch(`/api${path}`, { method: 'POST', ...init })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    const detail = typeof err?.detail === 'string' ? err.detail : null
    throw new Error(detail ?? `${res.status} ${res.statusText}`)
  }
  return { paper: await res.json(), existed: res.status === 200 }
}

function uploadPaper(file: File): Promise<UploadResult> {
  const body = new FormData()
  body.append('file', file)
  return createPaper('/papers', { body })
}

/** 웹 주소, arXiv ID, DOI로 가져오기 */
function importPaper(url: string): Promise<UploadResult> {
  return createPaper('/papers/import', {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
}

export const api = {
  listPapers: () => request<Paper[]>('/papers'),
  getBlocks: (paperId: string) => request<Block[]>(`/papers/${paperId}/blocks`),
  uploadPaper,
  importPaper,
  deletePaper: (paperId: string) => request<void>(`/papers/${paperId}`, { method: 'DELETE' }),
  fileUrl: (paperId: string) => `/api/papers/${paperId}/file`,
}
