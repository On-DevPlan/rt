import { Link } from 'react-router-dom'
import EndpointCard from '../components/EndpointCard.jsx'
import { bilibiliToolsEndpoints } from '../specs/bilibiliTools.js'
import styles from './crawlerPage.module.css'

export default function BilibiliToolsPage() {
  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <Link to="/crawlers" className={styles.backlink}>
          ← 返回 Crawler Cookbook
        </Link>
        <h1 className={styles.title}>Bilibili Tools</h1>
        <p className={styles.lede}>
          迁移自 <code>.claude/repo/BilibiliTools</code>。收藏夹 v3 枚举、批量收藏（写操作，需
          SESSDATA + bili_jct）、音频区三件套（单曲 CDN 直链 / 歌单 / UP 主歌曲）。
          私有收藏夹 → 403；csrf 失效 → 401。
        </p>
      </header>

      <div className={styles.cards}>
        {bilibiliToolsEndpoints.map((spec) => (
          <EndpointCard key={spec.id} spec={spec} />
        ))}
      </div>
    </div>
  )
}
