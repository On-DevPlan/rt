import { Suspense } from 'react'
import { getWidgetById, registry } from '../registry.js'

export function WidgetHost({ widgetId }) {
  const widget = getWidgetById(widgetId)

  if (!widget) {
    return (
      <div className="empty-card danger-tint">
        <h3>Widget 未找到</h3>
        <p>注册表里不存在 `{widgetId}`，请检查 `module.meta.js` 的 widgets 引用。</p>
      </div>
    )
  }

  return (
    <Suspense fallback={<div className="widget-card">正在加载组件 {widget.title}…</div>}>
      <div className="widget-card">
        <widget.Component widget={widget} registry={registry} />
      </div>
    </Suspense>
  )
}
