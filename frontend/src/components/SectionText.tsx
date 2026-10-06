import { RichText } from './RichText'

/** LLM이 쓴 섹션 텍스트. "- "로 시작하는 줄은 목록으로, 첨자 표기는 실제 첨자로. */
export function SectionText({ text }: { text: string }) {
  const groups: { list: boolean; lines: string[] }[] = []
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    if (!line) continue
    const list = line.startsWith('- ')
    const content = list ? line.slice(2) : line
    const last = groups.at(-1)
    if (last && last.list === list && list) last.lines.push(content)
    else groups.push({ list, lines: [content] })
  }
  return (
    <>
      {groups.map((g, i) =>
        g.list ? (
          <ul key={i}>
            {g.lines.map((l, j) => (
              <li key={j}>
                <RichText text={l} start={0} end={l.length} mark={null} />
              </li>
            ))}
          </ul>
        ) : (
          g.lines.map((l, j) => (
            <p key={`${i}-${j}`}>
              <RichText text={l} start={0} end={l.length} mark={null} />
            </p>
          ))
        ),
      )}
    </>
  )
}
