import { create } from 'zustand'
import type { BlockRange } from './lib/focus'

export type SideTab = 'translation' | 'explain' | 'mentions' | 'qa'
export type Scope = 'paper' | 'section' | 'paragraph' | 'selection'

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
  sideTab: SideTab
  scope: Scope
  zoom: number
  showBlocks: boolean
  openPaper: (paperId: string) => void
  setFocus: (focus: Focus | null) => void
  scrollToBlock: (blockId: string) => void
  setSideTab: (tab: SideTab) => void
  setScope: (scope: Scope) => void
  setZoom: (zoom: number) => void
  toggleShowBlocks: () => void
}

export const useReader = create<ReaderState>()((set) => ({
  paperId: null,
  focus: null,
  scrollTarget: null,
  sideTab: 'explain',
  scope: 'selection',
  zoom: 1.3,
  showBlocks: false,
  openPaper: (paperId) => set({ paperId, focus: null, scrollTarget: null }),
  setFocus: (focus) => set({ focus }),
  scrollToBlock: (blockId) => set({ scrollTarget: { blockId, nonce: Date.now() } }),
  setSideTab: (sideTab) => set({ sideTab }),
  setScope: (scope) => set({ scope }),
  setZoom: (zoom) => set({ zoom: Math.min(3, Math.max(0.6, zoom)) }),
  toggleShowBlocks: () => set((s) => ({ showBlocks: !s.showBlocks })),
}))
