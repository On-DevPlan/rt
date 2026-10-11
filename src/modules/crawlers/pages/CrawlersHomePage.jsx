import { Link } from 'react-router-dom'
import styles from './CrawlersHomePage.module.css'

const MODULES = [
  {
    route: '/crawlers/bilibili-crawler',
    name: 'bilibili-crawler',
    title: 'Bilibili Crawler',
    desc: 'WBI 签名、av↔bv、视频详情（分P）、播放直链、弹幕、两级评论（置顶+排序）、UP 动态与全量投稿。',
    endpoints: '10 个端点',
    source: 'Bilibili_crawler'
  },
  {
    route: '/crawlers/bilibili-tools',
    name: 'bilibili-tools',
    title: 'Bilibili Tools',
    desc: '收藏夹 v3 枚举、批量收藏（写操作）、音频区三件套（单曲 CDN / 歌单 / UP 歌曲）。',
    endpoints: '6 个端点',
    source: 'BilibiliTools'
  },
  {
    route: '/crawlers/skill-seekers',
    name: 'skill-seekers',
    title: 'Skill Seekers',
    desc: '文档站 BFS 爬取：sitemap → llms.txt 两层发现 + selector 回退链正文提取；可递归抓完直接打包 zip 下载。',
    endpoints: '2 个端点',
    source: 'Skill_Seekers'
  },
  {
    route: '/crawlers/mediacrawler',
    name: 'mediacrawler',
    title: 'Media Crawler',
    desc: '平台能力矩阵（7 平台）+ B 站关键词搜索（免登录核心，WBI 复用）；搜索支持贪心翻页归档下载。',
    endpoints: '3 个端点',
    source: 'MediaCrawler'
  }
]

const COOKBOOK_SECTIONS = [
  '0. 阅读对象与前置（后端启动命令）',
  '1. 端点速查表（4 模块 21 端点）',
  '2. 错误信封与排障规则（401/403/422/502 → 动作）',
  '3. 实用场景 ×11：两级评论 / 收藏夹导出 / 音频 CDN / 关键词搜索 / 文档站快照 / UP 投稿→评论链路 / 视频直链链路 / 批量收藏一条龙 / WBI 签名调试 / 文档站一键打包 / 贪心归档下载',
  '4. 前端 Explorer 与端点对应关系',
  '5. 部署侧注意事项（写操作鉴权 / 凭证不落盘）'
]

export default function CrawlersHomePage() {
  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <h1 className={styles.title}>Crawler Cookbook</h1>
        <p className={styles.lede}>
          后端 4 个爬虫模块（迁移自 <code>.claude/repo/</code> 下的 4 个仓库，共 21 个端点）的交互式
          API 浏览器。每个子页 = 参数表单 + 实时 curl 预览 + 响应 JSON。完整手册见仓库{' '}
          <code>docs/crawler-cookbook.md</code>。
        </p>
      </header>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>爬虫模块</h2>
        <div className={styles.grid}>
          {MODULES.map((m) => (
            <Link key={m.route} to={m.route} className={`panel ${styles.card}`}>
              <div className={styles.cardTop}>
                <span className={styles.name}>{m.name}</span>
                <span className={styles.count}>{m.endpoints}</span>
              </div>
              <h3>{m.title}</h3>
              <p>{m.desc}</p>
              <code className={styles.source}>来源：{m.source}</code>
            </Link>
          ))}
        </div>
      </section>

      <section className={`panel ${styles.cookbook}`}>
        <h2 className={styles.sectionTitle}>Cookbook 章节索引</h2>
        <ol className={styles.toc}>
          {COOKBOOK_SECTIONS.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ol>
        <p className={styles.note}>
          手册正文：<code>docs/crawler-cookbook.md</code> · 迁移决策：
          <code>docs/crawler-webapi-migration.md</code>
        </p>
      </section>
    </div>
  )
}
