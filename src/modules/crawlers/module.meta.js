import { defineModule, definePage } from '../../framework/schema.js'

export default defineModule({
  id: 'crawlers',
  title: 'Crawler API Explorer',
  description: '后端 4 个爬虫模块的交互式 API 浏览器：填参数、点提交、看响应。',
  order: 35,
  color: '#7a4a8c',
  pages: [
    definePage({
      id: 'crawlers-home',
      title: 'Crawler Cookbook',
      route: '/crawlers',
      entry: './pages/CrawlersHomePage.jsx',
      summary: 'cookbook 章节索引与 4 个爬虫子模块入口。',
      order: 0,
      tags: ['crawler', 'cookbook', 'api-explorer']
    }),
    definePage({
      id: 'bilibili-crawler',
      title: 'Bilibili Crawler',
      route: '/crawlers/bilibili-crawler',
      entry: './pages/BilibiliCrawlerPage.jsx',
      summary: 'WBI 签名、av↔bv 互转、视频信息、两级评论、UP 主空间动态。',
      order: 10,
      showcase: false,
      tags: ['bilibili', 'wbi', 'comments']
    }),
    definePage({
      id: 'bilibili-tools',
      title: 'Bilibili Tools',
      route: '/crawlers/bilibili-tools',
      entry: './pages/BilibiliToolsPage.jsx',
      summary: '收藏夹枚举与批量收藏、音频区（单曲 / 歌单 / UP 主歌曲）。',
      order: 20,
      showcase: false,
      tags: ['bilibili', 'favorites', 'audio']
    }),
    definePage({
      id: 'skill-seekers',
      title: 'Skill Seekers',
      route: '/crawlers/skill-seekers',
      entry: './pages/SkillSeekersPage.jsx',
      summary: '文档站 BFS 爬虫（sitemap + llms.txt 发现 + 正文提取）。',
      order: 30,
      showcase: false,
      tags: ['docs', 'bfs', 'scrape']
    }),
    definePage({
      id: 'mediacrawler',
      title: 'Media Crawler',
      route: '/crawlers/mediacrawler',
      entry: './pages/MediacrawlerPage.jsx',
      summary: '多平台能力矩阵 + B 站关键词搜索（免登录核心）。',
      order: 40,
      showcase: false,
      tags: ['mediacrawler', 'search', 'platforms']
    })
  ]
})
