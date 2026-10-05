import { create } from 'zustand'

export type SideTab = 'translation' | 'explain' | 'mentions' | 'qa'
export type Scope = 'paper' | 'section' | 'paragraph' | 'selection'

export interface TextSelection {
  text: string
  /** 선택 영역과 겹치는 블록 id (읽기 순서) */
  blockIds: string[]
}

interface ReaderState {
  paperId: string | null
  selection: TextSelection | null
  scrollTarget: { blockId: string; nonce: number } | null
  sideTab: SideTab
  scope: Scope
  zoom: number
  showBlocks: boolean
  openPaper: (paperId: string) => void
  setSelection: (selection: TextSelection | null) => void
  scrollToBlock: (blockId: string) => void
  setSideTab: (tab: SideTab) => void
  setScope: (scope: Scope) => void
  setZoom: (zoom: number) => void
  toggleShowBlocks: () => void
}

export const useReader = create<ReaderState>()((set) => ({
  paperId: null,
  selection: null,
  scrollTarget: null,
  sideTab: 'explain',
  scope: 'selection',
  zoom: 1.3,
  showBlocks: false,
  openPaper: (paperId) => set({ paperId, selection: null, scrollTarget: null }),
  setSelection: (selection) => set({ selection }),
  scrollToBlock: (blockId) => set({ scrollTarget: { blockId, nonce: Date.now() } }),
  setSideTab: (sideTab) => set({ sideTab }),
  setScope: (scope) => set({ scope }),
  setZoom: (zoom) => set({ zoom: Math.min(3, Math.max(0.6, zoom)) }),
  toggleShowBlocks: () => set((s) => ({ showBlocks: !s.showBlocks })),
}))
