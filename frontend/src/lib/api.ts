export type PaperStatus = 'parsing' | 'ready' | 'failed'
export type BlockType = 'heading' | 'paragraph' | 'caption' | 'figure'

export interface Paper {
  id: string
  title: string
  source_type: string
  source_url: string | null
  page_count: number
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
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init)
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail ?? `${res.status} ${res.statusText}`)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

export const api = {
  listPapers: () => request<Paper[]>('/papers'),
  getBlocks: (paperId: string) => request<Block[]>(`/papers/${paperId}/blocks`),
  uploadPaper: (file: File) => {
    const body = new FormData()
    body.append('file', file)
    return request<Paper>('/papers', { method: 'POST', body })
  },
  deletePaper: (paperId: string) => request<void>(`/papers/${paperId}`, { method: 'DELETE' }),
  fileUrl: (paperId: string) => `/api/papers/${paperId}/file`,
}
