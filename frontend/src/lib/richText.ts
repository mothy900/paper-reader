/** 파서가 남긴 첨자 표시(W_{Mt}, R^{2})를 화면용 조각으로 나눈다. */
export interface RichPiece {
  text: string
  kind: 'normal' | 'sub' | 'sup'
  /** 드래그한 범위와 겹치는지 */
  marked: boolean
}

const SCRIPT = /([_^])\{([^}]*)\}/g

/**
 * text[start:end]를 조각으로 나눈다. mark는 원문 오프셋 기준의 강조 범위.
 * 첨자 조각은 일부만 겹쳐도 통째로 강조한다(첨자 안을 쪼개 보여주지 않는다).
 */
export function richPieces(
  text: string,
  start: number,
  end: number,
  mark: { start: number; end: number } | null,
): RichPiece[] {
  const pieces: RichPiece[] = []
  const overlaps = (a: number, b: number) => mark !== null && a < mark.end && b > mark.start

  const pushNormal = (a: number, b: number) => {
    // 강조 경계에서 나눈다
    const cuts = [a, b]
    if (mark) for (const c of [mark.start, mark.end]) if (c > a && c < b) cuts.push(c)
    cuts.sort((x, y) => x - y)
    for (let i = 0; i < cuts.length - 1; i++) {
      const [s, e] = [cuts[i], cuts[i + 1]]
      if (e > s) pieces.push({ text: text.slice(s, e), kind: 'normal', marked: overlaps(s, e) })
    }
  }

  const segment = text.slice(start, end)
  let cursor = start
  for (const m of segment.matchAll(SCRIPT)) {
    const s = start + m.index
    const e = s + m[0].length
    pushNormal(cursor, s)
    pieces.push({ text: m[2], kind: m[1] === '_' ? 'sub' : 'sup', marked: overlaps(s, e) })
    cursor = e
  }
  pushNormal(cursor, end)
  return pieces
}
