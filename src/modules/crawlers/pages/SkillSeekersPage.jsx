import { Link } from 'react-router-dom'
import EndpointCard from '../components/EndpointCard.jsx'
import { skillSeekersEndpoints } from '../specs/skillSeekers.js'
import styles from './crawlerPage.module.css'

export default function SkillSeekersPage() {
  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <Link to="/crawlers" className={styles.backlink}>
          ← 返回 Crawler Cookbook
        </Link>
        <h1 className={styles.title}>Skill Seekers</h1>
        <p className={styles.lede}>
          迁移自 <code>.claude/repo/Skill_Seekers</code> 的 doc_scraper 核心：sitemap →
          llms.txt 两层发现 + BFS 抓正文（selector 回退链，与原仓库一致不回退 body）。
          dry_run 只做链接发现；最多 50 页；不执行 JS。
        </p>
      </header>

      <div className={styles.cards}>
        {skillSeekersEndpoints.map((spec) => (
          <EndpointCard key={spec.id} spec={spec} />
        ))}
      </div>
    </div>
  )
}
