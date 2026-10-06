import { useState } from 'react'
import type { Profile } from '../lib/api'
import { useSaveProfile } from '../lib/queries'

const LEVELS: { id: Profile['level']; label: string; hint: string }[] = [
  { id: 'beginner', label: '처음이에요', hint: '분야 용어부터 풀어서' },
  { id: 'intermediate', label: '기초는 알아요', hint: '핵심 개념 위주로' },
  { id: 'expert', label: '잘 알아요', hint: '간결하게' },
]

/** 해설을 내 수준에 맞추기 위한 정보. 첫 실행 때 묻고, 헤더에서 고칠 수 있다. */
export function ProfileDialog({ initial, onClose }: { initial: Profile | null; onClose: () => void }) {
  const [background, setBackground] = useState(initial?.background ?? '')
  const [level, setLevel] = useState<Profile['level']>(initial?.level ?? 'beginner')
  const save = useSaveProfile()

  return (
    <div className="dialog-backdrop" role="presentation">
      <form
        className="dialog"
        role="dialog"
        aria-labelledby="profile-title"
        onSubmit={(e) => {
          e.preventDefault()
          save.mutate({ background, level }, { onSuccess: onClose })
        }}
      >
        <h2 id="profile-title">해설을 내 수준에 맞추기</h2>
        <p className="muted">적어 주신 내용에 맞춰 설명의 깊이와 예시가 달라져요.</p>
        <label className="field">
          <span>배경지식</span>
          <textarea
            value={background}
            onChange={(e) => setBackground(e.target.value)}
            rows={3}
            placeholder="예: 웹 개발자, 고등학교 수학, 머신러닝은 입문 수준"
          />
        </label>
        <fieldset className="field">
          <legend>이 분야 논문은</legend>
          {LEVELS.map((l) => (
            <label key={l.id} className="choice">
              <input type="radio" name="level" checked={level === l.id} onChange={() => setLevel(l.id)} />
              {l.label} <span className="muted">· {l.hint}</span>
            </label>
          ))}
        </fieldset>
        {save.error && <p className="error">{save.error.message}</p>}
        <div className="dialog-actions">
          {initial && (
            <button type="button" onClick={onClose}>
              취소
            </button>
          )}
          <button type="submit" className="primary" disabled={save.isPending}>
            저장
          </button>
        </div>
      </form>
    </div>
  )
}
