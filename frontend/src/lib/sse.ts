export interface SseEvent {
  event: string
  data: unknown
}

/** POST로 SSE 스트림을 받는다 (EventSource는 GET만 지원해서 직접 파싱한다). */
export async function postSse(
  path: string,
  body: unknown,
  onEvent: (e: SseEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const res = await fetch(`/api${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => null)
    throw new Error(typeof err?.detail === 'string' ? err.detail : `${res.status} ${res.statusText}`)
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    let end: number
    while ((end = buffer.indexOf('\n\n')) !== -1) {
      const chunk = buffer.slice(0, end)
      buffer = buffer.slice(end + 2)
      let event = 'message'
      let data = ''
      for (const line of chunk.split('\n')) {
        if (line.startsWith('event: ')) event = line.slice(7)
        else if (line.startsWith('data: ')) data += line.slice(6)
      }
      onEvent({ event, data: data ? JSON.parse(data) : null })
    }
  }
}
