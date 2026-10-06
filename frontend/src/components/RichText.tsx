import { richPieces } from '../lib/richText'

/** 문장을 보여준다. 첨자 표시는 실제 첨자로, 드래그한 부분은 강조로. */
export function RichText({
  text,
  start,
  end,
  mark,
}: {
  text: string
  start: number
  end: number
  mark: { start: number; end: number } | null
}) {
  return (
    <>
      {richPieces(text, start, end, mark).map((p, i) => {
        const inner = p.kind === 'sub' ? <sub>{p.text}</sub> : p.kind === 'sup' ? <sup>{p.text}</sup> : p.text
        return p.marked ? <mark key={i}>{inner}</mark> : <span key={i}>{inner}</span>
      })}
    </>
  )
}
