import * as api from '../services/mediacrawlerApi.js'

const BASE = 'http://127.0.0.1:8080/api/mediacrawler'

export const mediacrawlerEndpoints = [
  {
    id: 'platforms',
    title: '平台能力矩阵',
    description: 'MediaCrawler 7 个平台的支持状态：哪些免登录可用（wrapped）、哪些需要浏览器登录态。无输入，直接提交。',
    method: 'GET',
    path: '/api/mediacrawler/platforms',
    inputs: [],
    buildCurl: () => `curl "${BASE}/platforms"`,
    submit: () => api.platforms()
  },
  {
    id: 'search',
    title: 'B 站关键词搜索',
    description: '/x/web-interface/wbi/search/type 的免登录包装，WBI 签名跨模块复用 bilibili_crawler。标题里的 <em> 高亮已剥除；仅取 result_type=video。无 cookie 时可能 -412 风控（→502），建议带 SESSDATA。',
    method: 'POST',
    path: '/api/mediacrawler/search',
    inputs: [
      { name: 'keyword', label: '关键词', type: 'text', placeholder: 'python 教程', default: 'python 教程' },
      { name: 'page', label: '页码', type: 'number', default: 1 },
      { name: 'page_size', label: '每页条数（≤50）', type: 'number', default: 20 },
      {
        name: 'order',
        label: '排序（对齐 SearchOrderType）',
        type: 'select',
        default: 'default',
        options: [
          { value: 'default', label: 'default — 综合排序' },
          { value: 'click', label: 'click — 最多点击' },
          { value: 'pubdate', label: 'pubdate — 最新发布' },
          { value: 'dm', label: 'dm — 弹幕最多' },
          { value: 'stow', label: 'stow — 最多收藏' }
        ]
      },
      { name: 'pubtime_begin_s', label: '发布时间过滤起点（秒级时间戳，0=不限）', type: 'number', default: 0 },
      { name: 'pubtime_end_s', label: '发布时间过滤终点（0=不限）', type: 'number', default: 0 },
      { name: 'sessdata', label: 'SESSDATA（可选，降风控）', type: 'text', sensitive: true }
    ],
    buildCurl: (v) =>
      `curl -X POST "${BASE}/search" -H "Content-Type: application/json" -d '${JSON.stringify(v)}'`,
    submit: (v) => api.searchBili(v)
  }
]
