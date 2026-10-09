import { create } from 'zustand'
import { queryClient } from './queryClient'
import { postSse } from './sse'

export type PrepKind = 'concepts' | 'data'
export type FieldStatus = 'stated' | 'inferred' | 'not_stated' | 'not_applicable'
export type EvidenceCheck = 'verified' | 'unverified' | 'image'

export interface Evidence {
  ref: string
  quote: string
  block_id: string | null
  check: EvidenceCheck
}

export interface DataField {
  value: string
  status: FieldStatus
  calculation: string
  evidence: Evidence[]
  numbers_unverified: string[]
}

export interface DataResult {
  applicable: boolean
  not_applicable_reason: string
  fields: Record<'inputs' | 'outputs' | 'sample_size' | 'validation' | 'metrics', DataField>
  warnings: { text: string; evidence: Evidence[] }[]
  questions: string[]
  supplementary: { block_id: string; snippet: string }[]
}

export interface Concept {
  name: string
  original: string
  what: string
  why: string
  section_ref: string
}

export interface ConceptsResult {
  concepts: Concept[]
}

export interface PrepState<T> {
  status: 'idle' | 'streaming' | 'done' | 'refused' | 'error'
  result?: T
  model?: string
  cached?: boolean
  costUsd?: number
  scope?: string
  tables?: string[]
  progress?: number
  message?: string
}

interface PrepStore {
  paperId: string | null
  concepts: PrepState<ConceptsResult>
  data: PrepState<DataResult>
  /** 저장된 결과로 채운다 (논문을 열 때, LLM 호출 없음) */
  load: (paperId: string, stored: { concepts: ConceptsResult | null; data: DataResult | null; data_scope: string }) => void
  run: (paperId: string, kind: PrepKind) => void
  reset: () => void
}

const IDLE = { status: 'idle' as const }
const ctrls = new Map<PrepKind, AbortController>()

export const usePrep = create<PrepStore>()((set, get) => ({
  paperId: null,
  concepts: IDLE,
  data: IDLE,
  load: (paperId, stored) => {
    if (get().paperId === paperId && (get().concepts.status !== 'idle' || get().data.status !== 'idle')) return
    set({
      paperId,
      concepts: stored.concepts ? { status: 'done', result: stored.concepts, cached: true, costUsd: 0 } : IDLE,
      data: stored.data
        ? { status: 'done', result: stored.data, cached: true, costUsd: 0, scope: stored.data_scope }
        : IDLE,
    })
  },
  run: (paperId, kind) => {
    ctrls.get(kind)?.abort()
    const ctrl = new AbortController()
    ctrls.set(kind, ctrl)
    const update = (patch: Partial<PrepState<never>>) => {
      if (!ctrl.signal.aborted) set((s) => ({ paperId, [kind]: { ...s[kind], ...patch } }))
    }
    set((s) => ({ paperId, [kind]: { ...s[kind], status: 'streaming', progress: 0, message: undefined } }))
    postSse(
      `/papers/${paperId}/prep/${kind}`,
      {},
      ({ event, data }) => {
        const d = data as Record<string, unknown>
        if (event === 'meta') update({ model: d.model as string, scope: d.scope as string, tables: d.tables as string[] })
        else if (event === 'progress') update({ progress: d.chars as number })
        else if (event === 'done')
          update({
            status: 'done',
            result: d.result as never,
            cached: d.cached as boolean,
            costUsd: d.cost_usd as number,
            model: d.model as string,
          })
        else if (event === 'refused' || event === 'error')
          update({ status: event === 'refused' ? 'refused' : 'error', message: d.message as string })
      },
      ctrl.signal,
    )
      .catch((err) => {
        if (!ctrl.signal.aborted) update({ status: 'error', message: err instanceof Error ? err.message : String(err) })
      })
      .finally(() => {
        void queryClient.invalidateQueries({ queryKey: ['usage', paperId] })
        // 응답이 끊겼으면 다시 시도할 수 있게
        set((s) => (s[kind].status === 'streaming' ? { [kind]: { ...s[kind], status: 'error', message: '응답이 중간에 끊겼어요.' } } : s))
      })
  },
  reset: () => {
    ctrls.forEach((c) => c.abort())
    ctrls.clear()
    set({ paperId: null, concepts: IDLE, data: IDLE })
  },
}))

export const DATA_FIELD_LABELS: [keyof DataResult['fields'], string][] = [
  ['inputs', '입력 X'],
  ['outputs', '출력 y'],
  ['sample_size', '샘플 수'],
  ['validation', '분할·검증'],
  ['metrics', '평가 지표'],
]

export const STATUS_LABELS: Record<FieldStatus, string> = {
  stated: '명시',
  inferred: '추정',
  not_stated: '명시 안 됨',
  not_applicable: '해당 없음',
}
