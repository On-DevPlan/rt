import { Link } from 'react-router-dom'
import EndpointCard from '../components/EndpointCard.jsx'
import { bilibiliCrawlerEndpoints } from '../specs/bilibiliCrawler.js'
import styles from './crawlerPage.module.css'

export default function BilibiliCrawlerPage() {
  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <Link to="/crawlers" className={styles.backlink}>
          ← 返回 Crawler Cookbook
        </Link>
        <h1 className={styles.title}>Bilibili Crawler</h1>
        <p className={styles.lede}>
          迁移自 <code>.claude/repo/Bilibili_crawler</code>（requests 脚本集）。WBI
          签名、av↔bv 互转、视频元信息、两级评论（含楼中楼）、UP 主空间动态。上游 <code>-101</code>{' '}
          → 401；风控 <code>412</code> → 502（提示带 SESSDATA）。
        </p>
      </header>

      <div className={styles.cards}>
        {bilibiliCrawlerEndpoints.map((spec) => (
          <EndpointCard key={spec.id} spec={spec} />
        ))}
      </div>
    </div>
  )
}
