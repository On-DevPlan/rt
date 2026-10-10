import * as api from '../services/bilibiliCrawlerApi.js'

const BASE = 'http://127.0.0.1:8080/api/bilibili-crawler'

export const bilibiliCrawlerEndpoints = [
  {
    id: 'convert',
    title: 'av ↔ bv 互转',
    description: '纯计算，无网络请求。aid 与 bvid 二选一（都传或都不传后端返回 422）。',
    method: 'GET',
    path: '/api/bilibili-crawler/convert',
    inputs: [
      { name: 'aid', label: 'aid（av 号）', type: 'number', placeholder: '170001' },
      { name: 'bvid', label: 'bvid（BV 号）', type: 'text', placeholder: 'BV17x411w7KC' }
    ],
    buildCurl: (v) => {
      const q = new URLSearchParams()
      if (v.aid !== undefined) q.set('aid', v.aid)
      if (v.bvid) q.set('bvid', v.bvid)
      return `curl "${BASE}/convert?${q}"`
    },
    submit: (v) => api.convert(v)
  },
  {
    id: 'wbi-sign',
    title: 'WBI 签名',
    description: '对任意业务参数计算 w_rid/wts（实时取 nav 接口的 img/sub key）。拿到签名后可自行请求任意需要 WBI 的 B 站接口。',
    method: 'POST',
    path: '/api/bilibili-crawler/wbi/sign',
    inputs: [
      {
        name: 'params',
        label: '业务参数（JSON 对象）',
        type: 'json',
        placeholder: '{"oid": 1504733402, "type": 1, "mode": 3}'
      }
    ],
    buildCurl: (v) =>
      `curl -X POST "${BASE}/wbi/sign" -H "Content-Type: application/json" -d '${JSON.stringify({ params: v.params })}'`,
    submit: (v) => api.wbiSign(v.params)
  },
  {
    id: 'video-info',
    title: '视频元信息',
    description: '标题 / UP 主 / 播放、点赞、投币等统计（view 接口）。',
    method: 'GET',
    path: '/api/bilibili-crawler/video/{bvid}',
    inputs: [{ name: 'bvid', label: 'bvid', type: 'text', placeholder: 'BV1xx411c7mD', default: 'BV1xx411c7mD' }],
    buildCurl: (v) => `curl "${BASE}/video/${encodeURIComponent(v.bvid)}"`,
    submit: (v) => api.videoInfo(v.bvid)
  },
  {
    id: 'comments',
    title: '两级评论',
    description: '一级评论分页 + 楼中楼展开。字段与原 Bilibili_crawler 脚本对齐（昵称/性别/时间/点赞/IP 属地/等级/uid/rpid）。',
    method: 'POST',
    path: '/api/bilibili-crawler/comments',
    inputs: [
      { name: 'oid', label: 'oid（type=1 视频为 aid；type=17 为动态 id）', type: 'text', placeholder: '170001', default: '170001' },
      {
        name: 'type',
        label: '评论区类型',
        type: 'select',
        default: 1,
        options: [
          { value: 1, label: '1 — 视频' },
          { value: 17, label: '17 — 动态' }
        ]
      },
      { name: 'ps', label: '每页条数（≤30）', type: 'number', default: 20 },
      { name: 'pages', label: '抓取页数（≤20）', type: 'number', default: 1 },
      { name: 'include_replies', label: '展开楼中楼', type: 'bool', default: true },
      { name: 'sessdata', label: 'SESSDATA（可选，降风控）', type: 'text', sensitive: true }
    ],
    buildCurl: (v) =>
      `curl -X POST "${BASE}/comments" -H "Content-Type: application/json" -d '${JSON.stringify(v)}'`,
    submit: (v) => api.fetchComments(v)
  },
  {
    id: 'user-space',
    title: 'UP 主空间动态',
    description: '动态列表，抽取每条的 comment_id_str / comment_type（可直接喂给上面的两级评论）。',
    method: 'POST',
    path: '/api/bilibili-crawler/user-space',
    inputs: [
      { name: 'mid', label: 'UP 主 uid', type: 'text', placeholder: '42', default: '42' },
      { name: 'max_pages', label: 'feed 翻页上限（≤20）', type: 'number', default: 3 },
      { name: 'sessdata', label: 'SESSDATA（可选）', type: 'text', sensitive: true }
    ],
    buildCurl: (v) =>
      `curl -X POST "${BASE}/user-space" -H "Content-Type: application/json" -d '${JSON.stringify(v)}'`,
    submit: (v) => api.fetchUserSpace(v)
  }
]
