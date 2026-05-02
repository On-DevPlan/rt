import { NavLink, Outlet } from 'react-router-dom'
import { registry } from '../registry.js'

function SidebarLink({ page }) {
  return (
    <NavLink
      to={page.route}
      className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
      onMouseEnter={() => page.preload?.()}
      onFocus={() => page.preload?.()}
    >
      <strong>{page.title}</strong>
      <span>{page.summary}</span>
    </NavLink>
  )
}

export function AppShell() {
  return (
    <div className="app-shell">
      <div className="shell-grid">
        <aside className="shell-sidebar">
          <div className="brand">
            <span className="brand-kicker">React Registry Kernel</span>
            <h1>RT</h1>
            <p>
              模块在各自目录内维护元数据、页面和组件。
              发现阶段只读取轻量 metadata，渲染阶段再懒加载真正的页面块。
            </p>
          </div>

          <div className="module-nav">
            {registry.modules.map((moduleRecord) => (
              <section key={moduleRecord.id} className="module-nav-section">
                <h2 className="module-nav-title">
                  <span>{moduleRecord.title}</span>
                  <span>{moduleRecord.pageIds.length}</span>
                </h2>

                <div className="module-nav-links">
                  {moduleRecord.pageIds.map((pageId) => (
                    <SidebarLink key={pageId} page={registry.pagesById.get(pageId)} />
                  ))}
                </div>
              </section>
            ))}
          </div>

          <div className="sidebar-footer">
            <div>modules: {registry.stats.moduleCount}</div>
            <div>pages: {registry.stats.pageCount}</div>
            <div>widgets: {registry.stats.widgetCount}</div>
            <div>dev port: 81</div>
          </div>
        </aside>

        <main className="shell-main">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
