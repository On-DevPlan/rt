import { Suspense } from 'react'
import { registry } from '../registry.js'
import { useDocumentTitle } from '../hooks/useDocumentTitle.js'
import { WidgetHost } from './WidgetHost.jsx'

export function PageFrame({ page }) {
  useDocumentTitle(page.title)

  return (
    <div className="page-stack">
      <div className="content-grid">
        <section className="panel">
          <Suspense fallback={<div className="screen-state">正在加载页面模块…</div>}>
            <page.Component page={page} registry={registry} />
          </Suspense>
        </section>

        <aside className="widget-section">
          {page.widgets.length > 0 ? (
            page.widgets.map((widgetId) => (
              <WidgetHost key={widgetId} widgetId={widgetId} />
            ))
          ) : (
            <div className="empty-card">
              <h3>无挂载组件</h3>
              <p>这个页面没有声明额外 widgets。你可以在对应的 `module.meta.js` 里直接补充。</p>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
