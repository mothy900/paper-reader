import { Group, Panel, Separator, useDefaultLayout } from 'react-resizable-panels'
import { Header } from './components/Header'
import { LeftSidebar } from './components/LeftSidebar'
import { PdfViewer } from './components/PdfViewer'
import { SideInfo } from './components/SideInfo'
import { useReader } from './store'

export default function App() {
  const paperId = useReader((s) => s.paperId)
  const layout = useDefaultLayout({ id: 'reader-main', storage: localStorage })

  return (
    <div className="app">
      <Header />
      <Group
        orientation="horizontal"
        className="workspace"
        defaultLayout={layout.defaultLayout}
        onLayoutChanged={layout.onLayoutChanged}
      >
        <Panel id="sidebar" defaultSize="18" minSize={180} collapsible>
          <LeftSidebar />
        </Panel>
        <Separator className="separator" />
        <Panel id="viewer" defaultSize="52" minSize={320}>
          {paperId ? (
            <PdfViewer key={paperId} paperId={paperId} />
          ) : (
            <div className="viewer-message">왼쪽에서 PDF를 열어 주세요.</div>
          )}
        </Panel>
        <Separator className="separator" />
        <Panel id="side-info" defaultSize="30" minSize={280} collapsible>
          <SideInfo />
        </Panel>
      </Group>
    </div>
  )
}
