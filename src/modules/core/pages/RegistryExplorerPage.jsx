import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

function matches(record, keyword) {
  const text = [
    record.id,
    record.title,
    record.summary,
    record.moduleTitle,
    ...(record.tags || [])
  ]
    .join(' ')
    .toLowerCase()

  return text.includes(keyword)
}

export default function RegistryExplorerPage({ registry }) {
  const [query, setQuery] = useState('')

  const keyword = query.trim().toLowerCase()
  const pages = useMemo(
    () => (keyword ? registry.pages.filter((record) => matches(record, keyword)) : registry.pages),
    [keyword, registry.pages]
  )
  const widgets = useMemo(
    () => (keyword ? registry.widgets.filter((record) => matches(record, keyword)) : registry.widgets),
    [keyword, registry.widgets]
  )

  return (
    <div className="page-stack">
      <div className="toolbar">
        <input
          className="search-input"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索 page / widget / tag / module"
        />
        <span className="subtle">
          当前结果: {pages.length} pages, {widgets.length} widgets
        </span>
      </div>

      <section className="registry-grid">
        {pages.map((page) => (
          <article key={page.id} className="registry-card">
            <h3>{page.title}</h3>
            <p>{page.summary}</p>
            <div className="hero-meta">
              <span className="tag">{page.moduleTitle}</span>
              <span className="tag">{page.route}</span>
            </div>
            <Link
              to={page.route}
              className="card-link"
              onMouseEnter={() => page.preload?.()}
              onFocus={() => page.preload?.()}
            >
              打开页面
            </Link>
          </article>
        ))}
      </section>

      <section className="widget-grid">
        {widgets.map((widget) => (
          <article key={widget.id} className="registry-card">
            <h3>{widget.title}</h3>
            <p>{widget.summary}</p>
            <div className="hero-meta">
              <span className="tag">{widget.moduleTitle}</span>
              <span className="tag">{widget.entry}</span>
            </div>
          </article>
        ))}
      </section>

      <section className="code-panel">
        <h3>为什么这个版本更快</h3>
        <pre>{`1. 启动时只 eager 导入 module.meta.js。
2. 页面组件和 widgets 仍是 split chunk，首次访问时才请求。
3. sidebar / card hover 预加载对应 chunk，减少二次跳转等待。
4. registry 在模块加载阶段同步生成，不再额外执行一次异步扫描流程。`}</pre>
      </section>
    </div>
  )
}
