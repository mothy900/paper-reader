/** 목록에 쓰는 짧은 날짜: 오늘이면 "오늘 14:05", 올해면 "10월 6일", 그 전이면 "2025. 3. 2." */
export function formatAddedAt(iso: string, now: Date = new Date()): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  if (d.toDateString() === now.toDateString()) {
    return `오늘 ${d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false })}`
  }
  if (d.getFullYear() === now.getFullYear()) {
    return d.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
  }
  return d.toLocaleDateString('ko-KR')
}
