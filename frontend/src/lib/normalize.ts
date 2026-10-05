/**
 * 텍스트 정규화. backend/app/text/normalize.py와 동작이 같아야 한다.
 * 두 구현은 shared/normalize_cases.json의 같은 케이스로 테스트한다.
 */
const QUOTES: Record<string, string> = { '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"' }

export function normalize(text: string): string {
  return text
    .normalize('NFKC') // 합자(ﬁ → fi), 전각 문자 등
    .replace(/\u00ad|\u200b|\u200c|\u200d|\ufeff/g, '') // 소프트 하이픈, zero-width 문자
    .replace(/\u2018|\u2019|\u201c|\u201d/g, (q) => QUOTES[q])
    .replace(/\s+/g, ' ')
    .trim()
}
