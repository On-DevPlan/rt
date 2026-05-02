import { Link } from 'react-router-dom'
import { useDocumentTitle } from '../hooks/useDocumentTitle.js'

export function NotFoundPage() {
  useDocumentTitle('页面不存在')

  return (
    <div className="page-stack">
      <section className="hero-panel">
        <span className="hero-topline">404</span>
        <h2>页面没有被注册</h2>
        <p>如果这是一个新页面，优先检查它是否已经进入某个 `module.meta.js` 的 `pages` 数组。</p>
        <Link to="/" className="card-link">
          返回首页
        </Link>
      </section>
    </div>
  )
}
