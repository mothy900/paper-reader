import { useEffect } from 'react'
import { useProfile } from '../lib/queries'
import type { SettingKey } from '../store'
import { useReader } from '../store'
import { ProfileForm } from './ProfileDialog'

const READING: { key: SettingKey; label: string; hint: string }[] = [
  {
    key: 'autoExplain',
    label: '드래그하면 바로 해설',
    hint: '끄면 드래그해도 해설을 요청하지 않아요. 해설 탭의 버튼으로 요청할 수 있어요. 드래그하며 읽는 습관이 있다면 꺼 두세요.',
  },
  {
    key: 'abbrTooltip',
    label: '약어 풀이',
    hint: '본문과 해설에서 약어에 마우스를 올리면 풀네임을 보여줘요.',
  },
]

/** 읽기 동작(브라우저에 저장, 바로 적용) + 내 정보(서버에 저장) + 개발용. */
export function SettingsDialog({ onClose }: { onClose: () => void }) {
  const settings = { autoExplain: useReader((s) => s.autoExplain), abbrTooltip: useReader((s) => s.abbrTooltip) }
  const setSetting = useReader((s) => s.setSetting)
  const showBlocks = useReader((s) => s.showBlocks)
  const toggleShowBlocks = useReader((s) => s.toggleShowBlocks)
  const profile = useProfile()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="dialog-backdrop" role="presentation" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog settings" role="dialog" aria-labelledby="settings-title">
        <h2 id="settings-title">설정</h2>
        <section className="settings-section">
          <h3 className="section-label">읽기 동작</h3>
          {READING.map((r) => (
            <label key={r.key} className="setting">
              <input type="checkbox" checked={settings[r.key]} onChange={(e) => setSetting(r.key, e.target.checked)} />
              <span>
                {r.label}
                <span className="muted setting-hint">{r.hint}</span>
              </span>
            </label>
          ))}
        </section>
        <section className="settings-section">
          <h3 className="section-label">내 정보</h3>
          <p className="muted">적어 주신 내용에 맞춰 설명의 깊이와 예시가 달라져요.</p>
          {profile.isSuccess && <ProfileForm initial={profile.data} submitLabel="내 정보 저장" />}
        </section>
        <details className="settings-section">
          <summary className="muted">개발용</summary>
          <label className="setting">
            <input type="checkbox" checked={showBlocks} onChange={toggleShowBlocks} />
            <span>
              블록 경계 보기
              <span className="muted setting-hint">파서가 나눈 블록과 id를 본문 위에 그려요.</span>
            </span>
          </label>
        </details>
        <div className="dialog-actions">
          <button type="button" onClick={onClose}>
            닫기
          </button>
        </div>
      </div>
    </div>
  )
}
