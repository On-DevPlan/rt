import { useState } from 'react'
import { ISLAND_CUT_TABS } from '../schemes.js'
import { IslandCutNavBar } from '../components/IslandCutNavBar.jsx'
import ImageCutPanel from './ImageCutPanel.jsx'
import VideoGifPanel from './VideoGifPanel.jsx'
import VideoApngPanel from './VideoApngPanel.jsx'

const PANEL_BY_ID = {
  'image-cut': ImageCutPanel,
  'video-gif': VideoGifPanel,
  'video-apng': VideoApngPanel,
}

export default function IslandCutPage() {
  const [activeId, setActiveId] = useState(ISLAND_CUT_TABS[0].id)
  return (
    <div className="page-stack">
      <IslandCutNavBar tabs={ISLAND_CUT_TABS} activeId={activeId} onChange={setActiveId} />
      {ISLAND_CUT_TABS.map((t) => {
        const Panel = PANEL_BY_ID[t.id]
        return (
          <div key={t.id} role="tabpanel" hidden={t.id !== activeId} style={{ width: '100%' }}>
            {Panel && <Panel />}
          </div>
        )
      })}
    </div>
  )
}