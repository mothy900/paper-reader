import { create } from 'zustand'
import type { Focus } from '../store'
import { queryClient } from './queryClient'
import { postSse } from './sse'

export type Detail = 'basic' | 'deep'
export type LlmStatus = 'idle' | 'streaming' | 'done' | 'refused' | 'error'

export interface LlmState {
  status: LlmStatus
  task?: string
  model?: string
  cached?: boolean
  sections: Record<string, string>
  costUsd?: number
  truncated?: boolean
  message?: string
}

export const IDLE: LlmState = { status: 'idle', sections: {} }

/** 서버가 보내는 SSE 이벤트를 상태로 접는다. */
export function reduceEvent(state: LlmState, event: string, data: Record<string, unknown>): LlmState {
  switch (event) {
    case 'meta':
      return { ...state, task: data.task as string, model: data.model as string, cached: data.cached as boolean }
    case 'section': {
      const name = data.name as string
      return { ...state, sections: { ...state.sections, [name]: (state.sections[name] ?? '') + (data.delta as string) } }
    }
    case 'done':
      return {
        ...state,
        status: 'done',
        model: data.model as string,
        cached: data.cached as boolean,
        costUsd: data.cost_usd as number,
        truncated: Boolean(data.truncated),
      }
    case 'refused':
      // 거절 전에 받은 조각은 완성된 답이 아니므로 버린다
      return { ...state, status: 'refused', sections: {}, message: data.message as string }
    case 'error':
      return { ...state, status: 'error', message: data.message as string }
    default:
      return state
  }
}

/** 스트림 하나를 돌리며 상태를 갱신한다. 취소되면 조용히 끝난다. */
async function runStream(
  path: string,
  body: unknown,
  signal: AbortSignal,
  update: (fn: (s: LlmState) => LlmState) => void,
  paperId: string,
): Promise<void> {
  update(() => ({ status: 'streaming', sections: {} }))
  try {
    await postSse(path, body, (e) => update((s) => reduceEvent(s, e.event, e.data as Record<string, unknown>)), signal)
    update((s) => (s.status === 'streaming' ? { ...s, status: 'error', message: '응답이 중간에 끊겼어요.' } : s))
  } catch (err) {
    if (signal.aborted) return
    update((s) => ({ ...s, status: 'error', message: err instanceof Error ? err.message : String(err) }))
  } finally {
    void queryClient.invalidateQueries({ queryKey: ['usage', paperId] })
  }
}

/** 서버 API 형식(snake_case)으로 */
export function toApiFocus(f: Focus) {
  return {
    source: f.source,
    text: f.text,
    block_ids: f.blockIds,
    ranges: f.ranges.map((r) => ({ block_id: r.blockId, start: r.start, end: r.end })),
    sentence_ids: f.sentenceIds,
  }
}

export type ApiFocus = ReturnType<typeof toApiFocus>

export function fromApiFocus(f: ApiFocus): Focus {
  return {
    source: f.source,
    text: f.text,
    blockIds: f.block_ids,
    ranges: f.ranges.map((r) => ({ blockId: r.block_id, start: r.start, end: r.end })),
    sentenceIds: f.sentence_ids,
  }
}

interface ExplainStore extends LlmState {
  detail: Detail
  run: (paperId: string, focus: Focus, detail: Detail) => void
  reset: () => void
}

let explainCtrl: AbortController | null = null

/** 해설 패널 상태. 포커스가 바뀌는 이벤트에서 바로 요청을 시작한다. */
export const useExplain = create<ExplainStore>()((set) => ({
  ...IDLE,
  detail: 'basic',
  run: (paperId, focus, detail) => {
    explainCtrl?.abort()
    const ctrl = (explainCtrl = new AbortController())
    set({ detail })
    void runStream(
      `/papers/${paperId}/explain`,
      { focus: toApiFocus(focus), detail },
      ctrl.signal,
      (fn) => {
        if (!ctrl.signal.aborted) set((s) => fn(s))
      },
      paperId,
    ).then(() => queryClient.invalidateQueries({ queryKey: ['history', paperId] }))
  },
  reset: () => {
    explainCtrl?.abort()
    explainCtrl = null
    set({ ...IDLE, detail: 'basic' })
  },
}))

interface TranslateStore {
  byBlock: Record<string, LlmState>
  run: (paperId: string, blockId: string) => void
  reset: () => void
}

const translateCtrls = new Map<string, AbortController>()

/** 문단 번역 상태 (문단별). 서버가 결과를 캐시하므로 다시 눌러도 비용이 들지 않는다. */
export const useTranslations = create<TranslateStore>()((set) => ({
  byBlock: {},
  run: (paperId, blockId) => {
    translateCtrls.get(blockId)?.abort()
    const ctrl = new AbortController()
    translateCtrls.set(blockId, ctrl)
    void runStream(
      `/papers/${paperId}/translate`,
      { block_id: blockId },
      ctrl.signal,
      (fn) => {
        if (!ctrl.signal.aborted) set((s) => ({ byBlock: { ...s.byBlock, [blockId]: fn(s.byBlock[blockId] ?? IDLE) } }))
      },
      paperId,
    )
  },
  reset: () => {
    translateCtrls.forEach((c) => c.abort())
    translateCtrls.clear()
    set({ byBlock: {} })
  },
}))

/** 0.2¢, $0.12 처럼 */
export function formatCost(usd: number): string {
  if (usd === 0) return '무료'
  const cents = usd * 100
  return cents < 100 ? `${cents < 0.1 ? cents.toFixed(2) : cents.toFixed(1)}¢` : `$${usd.toFixed(2)}`
}

export function modelLabel(model?: string): string {
  if (!model) return ''
  if (model.startsWith('claude-haiku')) return 'Haiku'
  if (model.startsWith('claude-sonnet')) return 'Sonnet'
  return model
}
