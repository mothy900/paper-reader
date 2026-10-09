import { useState } from 'react'
import { formatCost } from '../lib/llm'
import { usePapers, useProfile, useUsage } from '../lib/queries'
import { useReader } from '../store'
import { ProfileDialog } from './ProfileDialog'

interface HeaderProps {
  sidebarOpen: boolean
  sideOpen: boolean
  onToggleSidebar: () => void
  onToggleSide: () => void
}

export function Header({ sidebarOpen, sideOpen, onToggleSidebar, onToggleSide }: HeaderProps) {
  const paperId = useReader((s) => s.paperId)
  const zoom = useReader((s) => s.zoom)
  const setZoom = useReader((s) => s.setZoom)
  const showBlocks = useReader((s) => s.showBlocks)
  const toggleShowBlocks = useReader((s) => s.toggleShowBlocks)
  const { data: papers } = usePapers()
  const paper = papers?.find((p) => p.id === paperId)
  const { data: usage } = useUsage(paperId)
  const profile = useProfile()
  const [editing, setEditing] = useState(false)
  // 프로필을 아직 입력하지 않았으면 첫 실행 안내로 띄운다
  const showProfile = editing || (profile.isSuccess && profile.data === null)

  return (
    <header className="header">
      <button
        type="button"
        className="header-button"
        aria-pressed={sidebarOpen}
        onClick={onToggleSidebar}
        title={sidebarOpen ? '목차 닫기' : '목차 열기'}
      >
        목차
      </button>
      <span className="brand">Reader</span>
      <span className="header-title" title={paper?.title}>
        {paper?.title ?? ''}
      </span>
      {paper && paper.hidden_text_count > 0 && (
        <span
          className="header-notice"
          title="흰 글씨·아주 작은 글씨처럼 사람 눈에 보이지 않는 텍스트입니다. AI를 조작하려는 문구일 수 있어 해설·번역에서 제외했습니다."
        >
          숨은 텍스트 {paper.hidden_text_count}곳을 제외했습니다
        </span>
      )}
      {paper?.language === 'ko' && (
        <span className="header-notice">한국어 논문은 아직 일부 기능만 지원합니다</span>
      )}
      {usage && usage.calls > 0 && (
        <span className="header-cost" title={`이 논문에서 LLM을 ${usage.calls}번 호출했어요`}>
          이 논문 {formatCost(usage.cost_usd)}
        </span>
      )}
      <button type="button" className="header-button" onClick={() => setEditing(true)}>
        내 정보
      </button>
      <button
        type="button"
        className="header-button"
        aria-pressed={sideOpen}
        onClick={onToggleSide}
        title={sideOpen ? '해설 패널 닫기' : '해설 패널 열기'}
      >
        해설 패널
      </button>
      {showProfile && <ProfileDialog initial={profile.data ?? null} onClose={() => setEditing(false)} />}
      {paper && (
        <div className="header-tools">
          <label className="toggle">
            <input type="checkbox" checked={showBlocks} onChange={toggleShowBlocks} />
            블록 경계
          </label>
          <button type="button" onClick={() => setZoom(zoom - 0.1)} aria-label="축소">
            −
          </button>
          <span className="zoom">{Math.round(zoom * 100)}%</span>
          <button type="button" onClick={() => setZoom(zoom + 0.1)} aria-label="확대">
            +
          </button>
        </div>
      )}
    </header>
  )
}
