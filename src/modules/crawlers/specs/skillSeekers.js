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
      { name: 'dry_run', label: 'dry-run（只发现不保存正文）', type: 'bool', default: false },
      {
        name: 'categorize',
        label: '分类聚合（响应附带 categories + quick_reference）',
        type: 'bool',
        default: false
      },
      {
        name: 'categories',
        label: '分类配置 JSON（可选；缺省走 URL 段推断）',
        type: 'json',
        placeholder: '{"guide": ["guide", "入门"], "api": ["api", "reference"]}'
      }
    ],
    buildCurl: (v) =>
      `curl -X POST "${BASE}/scrape" -H "Content-Type: application/json" -d '${JSON.stringify(v)}'`,
    submit: (v) => api.scrape(v)
  },
  {
    id: 'scrape-archive',
    title: '文档站打包下载（递归抓取 → zip）',
    description: '同一条 BFS 管线递归抓完后，服务端直接打包 zip 下载：README.md 索引 + pages/*.md（每页一个 markdown，含标题/正文/代码块/链接）+ categories.json / quick_reference.md。范围限定在 base_url 目录前缀内——要整站就填文档根（如 https://x.com/docs/）。include/exclude 是子串匹配（如 v2 命中 v2-advance）。max_pages ≤200，串行抓取注意耗时。',
    method: 'POST',
    path: '/api/skill-seekers/scrape/archive',
    download: true,
    inputs: [
      { name: 'base_url', label: '起始 URL（整站填文档根）', type: 'text', placeholder: 'https://docs.example.com/docs/' },
      {
        name: 'scope',
        label: '范围语义',
        type: 'select',
        default: 'auto',
        options: [
          { value: 'auto', label: 'auto — 叶子起始页自动放宽到所在目录' },
          { value: 'strict', label: 'strict — 严格目录前缀（原仓库语义）' }
        ]
      },
      { name: 'max_pages', label: '最多抓取页数（≤200）', type: 'number', default: 50 },
      { name: 'rate_limit', label: '每页间隔秒数', type: 'number', default: 0.2 },
      { name: 'include_patterns', label: 'URL 必须命中的子串（每行一个，可空）', type: 'list', placeholder: 'v2' },
      { name: 'exclude_patterns', label: 'URL 命中即排除（每行一个，可空）', type: 'list', placeholder: 'deprecated\n/blog/' },
      { name: 'selector', label: '正文 CSS selector（可选）', type: 'text', placeholder: 'div.theme-doc-markdown' },
      { name: 'use_sitemap', label: '探测 sitemap.xml', type: 'bool', default: true },
      { name: 'use_llms_txt', label: 'sitemap 无结果时探测 llms.txt', type: 'bool', default: true },
      { name: 'categorize', label: '包内附带 categories.json + quick_reference.md', type: 'bool', default: true },
      {
        name: 'categories',
        label: '分类配置 JSON（可选；缺省走 URL 段推断）',
        type: 'json',
        placeholder: '{"guide": ["guide", "入门"], "api": ["api", "reference"]}'
      }
    ],
    buildCurl: (v) =>
      `curl -X POST "${BASE}/scrape/archive" -H "Content-Type: application/json" -o docs-archive.zip -d '${JSON.stringify(v)}'`,
    submit: (v) => api.archive(v)
  }
]
