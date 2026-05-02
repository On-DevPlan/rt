import { Link } from 'react-router-dom'
import { registry } from '../framework/registry.js'
import { useDocumentTitle } from '../framework/hooks/useDocumentTitle.js'

function ShowcaseCard({ page }) {
  return (
    <article
      className="showcase-card"
      onMouseEnter={() => page.preload?.()}
      onFocus={() => page.preload?.()}
    >
      <div className="showcase-card-top">
        <span className="showcase-module">{page.moduleTitle}</span>
        <span className="showcase-card-badge">Fullscreen</span>
      </div>
      <div className="showcase-card-body">
        <h3>{page.title}</h3>
        <p>{page.summary}</p>
      </div>
      <div className="showcase-tags">
        {page.tags.slice(0, 4).map((tag) => (
          <span key={tag} className="showcase-tag">
            {tag}
          </span>
        ))}
      </div>
      <div className="showcase-card-bottom">
        <span className="showcase-route-label">component page</span>
        <Link className="showcase-link" to={page.route}>
          Open
        </Link>
      </div>
    </article>
  )
}

export default function HomePage() {
  useDocumentTitle('Components')

  const showcasePages = registry.pages.filter((page) => !page.internal && page.showcase !== false)
  const moduleCount = new Set(showcasePages.map((page) => page.moduleId)).size

  return (
    <div className="home-stage">
      <section className="home-toolbar">
        <div className="home-toolbar-copy">
          <span className="home-kicker">RT Components</span>
          <h1>组件总览</h1>
        </div>
        <div className="home-toolbar-stats">
          <div className="home-stat-chip">
            <strong>{showcasePages.length}</strong>
            <span>components</span>
          </div>
          <div className="home-stat-chip">
            <strong>{moduleCount}</strong>
            <span>modules</span>
          </div>
          <div className="home-stat-chip">
            <strong>81</strong>
            <span>port</span>
          </div>
        </div>
      </section>

      {showcasePages.length > 0 ? (
        <section className="showcase-grid">
          {showcasePages.map((page) => (
            <ShowcaseCard key={page.id} page={page} />
          ))}
        </section>
      ) : (
        <section className="empty-card">
          <h3>No Components Yet</h3>
          <p>当前还没有对外展示的组件页面。</p>
        </section>
      )}
    </div>
  )
}
