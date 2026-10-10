import { Link } from 'react-router-dom'
import EndpointCard from '../components/EndpointCard.jsx'
import { mediacrawlerEndpoints } from '../specs/mediacrawler.js'
import styles from './crawlerPage.module.css'

export default function MediacrawlerPage() {
  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <Link to="/crawlers" className={styles.backlink}>
          ← 返回 Crawler Cookbook
        </Link>
        <h1 className={styles.title}>Media Crawler</h1>
        <p className={styles.lede}>
          迁移自 <code>.claude/repo/MediaCrawler</code> 的免登录核心：平台能力矩阵 +
          B 站关键词搜索（WBI 签名跨模块复用 bilibili_crawler）。其余 6 平台需浏览器登录态，
          见「平台能力矩阵」的 wrapped 字段。
        </p>
      </header>

      <div className={styles.cards}>
        {mediacrawlerEndpoints.map((spec) => (
          <EndpointCard key={spec.id} spec={spec} />
        ))}
      </div>
    </div>
  )
}
