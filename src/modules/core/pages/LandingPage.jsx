import { Link } from 'react-router-dom'

const manifestSnippet = `export default defineModule({
  id: 'orders',
  pages: [
    definePage({
      id: 'dashboard',
      route: '/orders/dashboard',
      entry: './pages/DashboardPage.jsx',
      widgets: ['orders-health']
    })
  ],
  widgets: [
    defineWidget({
      id: 'orders-health',
      entry: './widgets/OrdersHealthWidget.jsx'
    })
  ]
})`

export default function LandingPage({ registry }) {
  return (
    <div className="page-stack">
      <section className="metrics-grid">
        <div className="panel">
          <div className="metric-value">{registry.stats.moduleCount}</div>
          <div className="metric-label">已发现模块</div>
        </div>
        <div className="panel">
          <div className="metric-value">{registry.stats.pageCount}</div>
          <div className="metric-label">自动注册页面</div>
        </div>
        <div className="panel">
          <div className="metric-value">{registry.stats.widgetCount}</div>
          <div className="metric-label">可挂载 widgets</div>
        </div>
      </section>

      <section className="module-grid">
        <article className="tip-card">
          <h3>发现机制</h3>
          <p>
            只同步导入 `module.meta.js`。页面和组件仍然通过 `import.meta.glob` 懒加载，
            避免像 `ve` 那样在启动期逐个异步扫描配置并串行等待。
          </p>
        </article>
        <article className="tip-card">
          <h3>元数据集中</h3>
          <p>
            每个模块只维护一个清晰的 manifest。页面路由、标签、挂载 widgets、
            加载入口都在一起，不需要在多个地方来回同步。
          </p>
        </article>
      </section>

      <section className="code-panel">
        <h3>建议的模块声明</h3>
        <pre>{manifestSnippet}</pre>
      </section>

      <section className="module-grid">
        {registry.modules.map((moduleRecord) => (
          <article key={moduleRecord.id} className="registry-card">
            <h3>{moduleRecord.title}</h3>
            <p>{moduleRecord.description}</p>
            <div className="hero-meta">
              <span className="tag">{moduleRecord.pageIds.length} pages</span>
              <span className="tag">{moduleRecord.widgetIds.length} widgets</span>
            </div>
          </article>
        ))}
      </section>

      <article className="tip-card">
        <h3>下一步</h3>
        <p>
          现在新增一个模块时，只需要放进 `src/modules/你的模块`，写好一个 `module.meta.js`，
          registry 和导航都会自动收录。
        </p>
        <Link to="/registry" className="card-link">
          查看自动发现结果
        </Link>
      </article>
    </div>
  )
}
