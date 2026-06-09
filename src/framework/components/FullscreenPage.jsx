import { Suspense } from 'react'
import { useDocumentTitle } from '../hooks/useDocumentTitle.js'
import { registry } from '../registry.js'

export function FullscreenPage({ page }) {
  useDocumentTitle(page.title)

  return (
    <Suspense fallback={<div className="screen-state">正在加载组件页面…</div>}>
      <page.Component page={page} registry={registry} />
    </Suspense>
  )
}
