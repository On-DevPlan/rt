import { Link } from 'react-router-dom'
import { registry } from '../framework/registry.js'
import { useDocumentTitle } from '../framework/hooks/useDocumentTitle.js'

function ShowcaseCard({ page, featured = false }) {
  return (
    <article
      className={`showcase-card${featured ? ' featured' : ''}`}
      onMouseEnter={() => page.preload?.()}
      onFocus={() => page.preload?.()}
    >
      <span className="showcase-module">{page.moduleTitle}</span>
      <h3>{page.title}</h3>
      <p>{page.summary}</p>
      <div className="showcase-tags">
        {page.tags.slice(0, 4).map((tag) => (
          <span key={tag} className="showcase-tag">
            {tag}
          </span>
        ))}
      </div>
      <Link className="showcase-link" to={page.route}>
        Open Fullscreen
      </Link>
    </article>
  )
}

export default function HomePage() {
  useDocumentTitle('Components')

  const showcasePages = registry.pages.filter((page) => !page.internal && page.showcase !== false)
  const [featuredPage, ...otherPages] = showcasePages

  return (
    <div className="home-stage">
      <section className="home-hero">
        <div className="home-hero-copy">
          <span className="home-kicker">RT Components</span>
          <h1>组件入口</h1>
          <p>
            只保留组件展示。进入后直接全屏查看单个组件，不暴露实现规则，不展示框架结构。
          </p>
        </div>
        <div className="home-hero-stats">
          <div className="home-stat">
            <strong>{showcasePages.length}</strong>
            <span>Live Components</span>
          </div>
          <div className="home-stat">
            <strong>81</strong>
            <span>Dev Port</span>
          </div>
        </div>
      </section>

      {featuredPage ? (
        <section className="showcase-grid">
          <ShowcaseCard page={featuredPage} featured />
          {otherPages.map((page) => (
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
