import * as api from '../services/skillSeekersApi.js'

const BASE = 'http://127.0.0.1:8080/api/skill-seekers'

export const skillSeekersEndpoints = [
  {
    id: 'scrape',
    title: '文档站 BFS 爬取',
    description: 'sitemap → llms.txt 两层发现 + BFS 抓正文。范围限定在 base_url 目录前缀内。dry_run 只做链接发现（pages 里是 {url, links} 记录，pages_saved=0）。不执行 JS，SPA 站点不可用。',
    method: 'POST',
    path: '/api/skill-seekers/scrape',
    inputs: [
      { name: 'base_url', label: '起始 URL（目录前缀）', type: 'text', placeholder: 'https://docs.example.com/guide/' },
      { name: 'max_pages', label: '最多抓取页数（≤50）', type: 'number', default: 10 },
      { name: 'rate_limit', label: '每页间隔秒数', type: 'number', default: 0.2 },
      { name: 'include_patterns', label: 'URL 必须命中的子串（每行一个，可空）', type: 'list', placeholder: '/v2/' },
      { name: 'exclude_patterns', label: 'URL 命中即排除（每行一个，可空）', type: 'list', placeholder: 'deprecated\n/blog/' },
      { name: 'selector', label: '正文 CSS selector（可选，缺省走回退链）', type: 'text', placeholder: 'div.theme-doc-markdown' },
      { name: 'use_sitemap', label: '探测 sitemap.xml', type: 'bool', default: true },
      { name: 'use_llms_txt', label: 'sitemap 无结果时探测 llms.txt', type: 'bool', default: true },
      { name: 'dry_run', label: 'dry-run（只发现不保存正文）', type: 'bool', default: false }
    ],
    buildCurl: (v) =>
      `curl -X POST "${BASE}/scrape" -H "Content-Type: application/json" -d '${JSON.stringify(v)}'`,
    submit: (v) => api.scrape(v)
  }
]
