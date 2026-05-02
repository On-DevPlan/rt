import { Suspense } from 'react'
import { Link } from 'react-router-dom'
import { useDocumentTitle } from '../hooks/useDocumentTitle.js'
import { registry } from '../registry.js'

export function FullscreenPage({ page }) {
  useDocumentTitle(page.title)

  return (
    <div className="fullscreen-page">
      <header className="fullscreen-header">
        <Link className="fullscreen-home-link" to="/">
          RT
        </Link>
        <div className="fullscreen-title-block">
          <span>{page.moduleTitle}</span>
          <strong>{page.title}</strong>
        </div>
        <Link className="fullscreen-back-link" to="/">
          Back to Components
        </Link>
      </header>

      <main className="fullscreen-canvas">
        <Suspense fallback={<div className="screen-state">正在加载组件页面…</div>}>
          <page.Component page={page} registry={registry} />
        </Suspense>
      </main>
    </div>
  )
}
