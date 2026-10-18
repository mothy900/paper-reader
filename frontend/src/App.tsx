import { useEffect, useState } from 'react'
import { Group, Panel, Separator, useDefaultLayout, usePanelRef } from 'react-resizable-panels'
import { Header } from './components/Header'
import { LeftSidebar } from './components/LeftSidebar'
import { PdfViewer } from './components/PdfViewer'
import { SideInfo } from './components/SideInfo'
import { paperIdFromUrl, useReader } from './store'

export default function App() {
  const paperId = useReader((s) => s.paperId)
  const openPaper = useReader((s) => s.openPaper)
  const layout = useDefaultLayout({ id: 'reader-main', storage: localStorage })
  const sidebarRef = usePanelRef()
  const sideRef = usePanelRef()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [sideOpen, setSideOpen] = useState(true)

  // 주소의 ?paper=… 로 논문을 연다 (새로고침·뒤로 가기에서도 열어 둔 논문 유지)
  useEffect(() => {
    const sync = () => openPaper(paperIdFromUrl(), { fromUrl: true })
    sync()
    window.addEventListener('popstate', sync)
    return () => window.removeEventListener('popstate', sync)
  }, [openPaper])

  const toggle = (ref: typeof sideRef) => {
    const panel = ref.current
    if (!panel) return
    if (panel.isCollapsed()) panel.expand()
    else panel.collapse()
  }

  return (
    <div className="app">
      <Header
        sidebarOpen={sidebarOpen}
        sideOpen={sideOpen}
        onToggleSidebar={() => toggle(sidebarRef)}
        onToggleSide={() => toggle(sideRef)}
      />
      <div className="workspace-wrap">
        <Group
          orientation="horizontal"
          className="workspace"
          defaultLayout={layout.defaultLayout}
          onLayoutChanged={layout.onLayoutChanged}
        >
          <Panel
            id="sidebar"
            panelRef={sidebarRef}
            defaultSize="18"
            minSize={180}
            collapsible
            onResize={(size) => setSidebarOpen(size.inPixels > 0)}
          >
            <LeftSidebar />
          </Panel>
          <Separator className="separator" />
          <Panel id="viewer" defaultSize="52" minSize={320}>
            {paperId ? (
              <PdfViewer key={paperId} paperId={paperId} />
            ) : (
              <div className="viewer-message">왼쪽에서 논문을 열어 주세요.</div>
            )}
          </Panel>
          <Separator className="separator" />
          <Panel
            id="side-info"
            panelRef={sideRef}
            defaultSize="30"
            minSize={280}
            collapsible
            onResize={(size) => setSideOpen(size.inPixels > 0)}
          >
            <SideInfo />
          </Panel>
        </Group>
        {/* 접힌 패널을 다시 여는 손잡이. 경계선만으로는 찾기 어렵다. */}
        {!sidebarOpen && (
          <button type="button" className="panel-rail left" onClick={() => sidebarRef.current?.expand()}>
            목차 열기
          </button>
        )}
        {!sideOpen && (
          <button type="button" className="panel-rail right" onClick={() => sideRef.current?.expand()}>
            해설 열기
          </button>
        )}
      </div>
    </div>
  )
}
