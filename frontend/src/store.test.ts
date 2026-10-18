import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useExplain } from './lib/llm'
import type { Focus } from './store'
import { useReader } from './store'

const drag: Focus = {
  source: 'selection',
  text: 'self-attention',
  blockIds: ['p1-2'],
  ranges: [{ blockId: 'p1-2', start: 0, end: 14 }],
  sentenceIds: ['p1-2:0'],
}
const click: Focus = { ...drag, source: 'block' }

describe('drag explain toggle', () => {
  const run = vi.fn()
  const reset = vi.fn()

  beforeEach(() => {
    run.mockClear()
    reset.mockClear()
    useExplain.setState({ run, reset })
    useReader.setState({ paperId: 'paper-1', focus: null, sideTab: 'explain', autoExplain: true })
  })

  it('explains right away when on', () => {
    useReader.getState().setFocus(drag)
    expect(run).toHaveBeenCalledWith('paper-1', drag, 'basic')
  })

  it('only sets the focus when off', () => {
    useReader.setState({ autoExplain: false })
    useReader.getState().setFocus(drag)
    expect(run).not.toHaveBeenCalled()
    expect(useReader.getState().focus).toBe(drag)
  })

  it('does not jump from the prep tab on drag when off, but does on click', () => {
    useReader.setState({ autoExplain: false, sideTab: 'prep' })
    useReader.getState().setFocus(drag)
    expect(useReader.getState().sideTab).toBe('prep')
    useReader.getState().setFocus(click)
    expect(useReader.getState().sideTab).toBe('explain')
    expect(run).not.toHaveBeenCalled() // 클릭은 원래 버튼으로 요청
  })
})
