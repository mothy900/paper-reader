import { create } from 'zustand'
import type { BlockRange } from './lib/focus'
import type { Detail } from './lib/llm'
import { useExplain, useTranslations } from './lib/llm'
import { usePrep } from './lib/prep'

export type SideTab = 'prep' | 'translation' | 'explain' | 'mentions' | 'qa'

/** 주소의 ?paper=… 값. 새로고침·뒤로 가기에서 열어 둔 논문을 유지하는 데 쓴다. */
export function paperIdFromUrl(): string | null {
  return new URLSearchParams(window.location.search).get('paper')
}

function writePaperToUrl(paperId: string | null) {
  const url = new URL(window.location.href)
  if (paperId) url.searchParams.set('paper', paperId)
  else url.searchParams.delete('paper')
  if (url.href !== window.location.href) window.history.pushState(null, '', url)
}

/**
 * 포커스: "지금 무엇에 대해 묻고 있나"의 기준. 사용자가 마지막으로 지정한 곳이다.
 * - selection: 드래그한 문구
 * - block: 클릭한 문단
 */
export interface Focus {
  source: 'selection' | 'block'
  text: string
  /** 포커스가 걸친 블록 id (읽기 순서) */
  blockIds: string[]
  /** 블록 텍스트 안의 정확한 범위 */
  ranges: BlockRange[]
  /** 범위와 겹치는 문장 id ("p3-12:2") */
  sentenceIds: string[]
}

interface ReaderState {
  paperId: string | null
  focus: Focus | null
  scrollTarget: { blockId: string; nonce: number } | null
  /** 근거 칩을 눌렀을 때 잠깐 강조할 블록 */
  flash: { blockId: string; nonce: number } | null
  sideTab: SideTab
  zoom: number
  showBlocks: boolean
  /** fromUrl: 주소에서 읽어 온 경우라 주소를 다시 쓰지 않는다 */
  openPaper: (paperId: string | null, opts?: { fromUrl?: boolean }) => void
  /** 사용자가 본문에서 포커스를 바꿨다. 해설 탭에서 드래그했으면 바로 해설을 요청한다. */
  setFocus: (focus: Focus | null) => void
  /** 해설 기록에서 다시 연다 (서버 캐시라 비용 없음) */
  reopenExplain: (focus: Focus, detail: Detail) => void
  scrollToBlock: (blockId: string) => void
  /** 스크롤하고 잠깐 강조한다 (포커스는 바꾸지 않는다) */
  flashBlock: (blockId: string) => void
  setSideTab: (tab: SideTab) => void
  setZoom: (zoom: number) => void
  toggleShowBlocks: () => void
}

export const useReader = create<ReaderState>()((set, get) => ({
  paperId: null,
  focus: null,
  scrollTarget: null,
  flash: null,
  sideTab: 'prep',
  zoom: 1.3,
  showBlocks: false,
  openPaper: (paperId, opts) => {
    if (!opts?.fromUrl) writePaperToUrl(paperId)
    if (paperId === get().paperId) return
    useExplain.getState().reset()
    useTranslations.getState().reset()
    usePrep.getState().reset()
    set({ paperId, focus: null, scrollTarget: null, sideTab: 'prep' })
  },
  setFocus: (focus) => {
    // 준비 탭에서 본문을 고르면 해설 탭으로 넘어간다
    if (focus && get().sideTab === 'prep') set({ sideTab: 'explain' })
    set({ focus })
    const { paperId, sideTab } = get()
    // 토큰 절약: 해설 탭을 보면서 드래그한 경우만 자동 요청. 문단 클릭은 버튼으로.
    if (paperId && focus?.source === 'selection' && focus.sentenceIds.length > 0 && sideTab === 'explain') {
      useExplain.getState().run(paperId, focus, 'basic')
    } else {
      useExplain.getState().reset()
    }
  },
  reopenExplain: (focus, detail) => {
    set({ focus, sideTab: 'explain' })
    const { paperId } = get()
    if (paperId) useExplain.getState().run(paperId, focus, detail)
  },
  scrollToBlock: (blockId) => set({ scrollTarget: { blockId, nonce: Date.now() } }),
  flashBlock: (blockId) => {
    const nonce = Date.now()
    set({ scrollTarget: { blockId, nonce }, flash: { blockId, nonce } })
  },
  setSideTab: (sideTab) => set({ sideTab }),
  setZoom: (zoom) => set({ zoom: Math.min(3, Math.max(0.6, zoom)) }),
  toggleShowBlocks: () => set((s) => ({ showBlocks: !s.showBlocks })),
}))
