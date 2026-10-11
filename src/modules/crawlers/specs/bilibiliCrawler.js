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
    title: '视频完整详情（view/detail）',
    description: 'aid 或 bvid 自适应。含标题/UP 主/统计 + 分P pages[]（每P 的 cid，是 play-url 与 danmaku 的前置入参）。',
    method: 'GET',
    path: '/api/bilibili-crawler/video/{video_id}',
    inputs: [
      { name: 'video_id', label: '视频 id（BV 号或纯数字 aid）', type: 'text', placeholder: 'BV1xx411c7mD', default: 'BV1xx411c7mD' },
      { name: 'sessdata', label: 'SESSDATA（可选）', type: 'text', sensitive: true }
    ],
    buildCurl: (v) =>
      `curl "${BASE}/video/${encodeURIComponent(v.video_id)}${v.sessdata ? `?sessdata=${v.sessdata}` : ''}"`,
    submit: (v) => api.videoInfo(v.video_id, { sessdata: v.sessdata })
  },
  {
    id: 'play-url',
    title: '播放直链 + 清晰度',
    description: 'WBI 签名 playurl。aid/cid 从「视频完整详情」的 pages[] 拿。qn：120=4K 116=1080P60 112=1080P+ 80=1080P 74=720P60 64=720P 32=480P 16=360P（高的多需 SESSDATA）。fnval=1 返回 mp4 合一直链（durl）；16=仅 DASH；4048=全部 DASH（无直链）。直链下载需带 B 站 Referer。响应含 timelength（片长 ms）与 support_formats[]（各清晰度 codecs 明细，DASH 选流用）。',
    method: 'POST',
    path: '/api/bilibili-crawler/play-url',
    inputs: [
      { name: 'aid', label: 'aid', type: 'number', placeholder: '170001' },
      { name: 'cid', label: '分P cid', type: 'number', placeholder: '9001' },
      {
        name: 'qn',
        label: '清晰度 qn',
        type: 'select',
        default: 80,
        options: [
          { value: 120, label: '120 — 4K（需 SESSDATA + fnval 含 128）' },
          { value: 116, label: '116 — 1080P60（需 SESSDATA）' },
          { value: 112, label: '112 — 1080P+（需 SESSDATA）' },
          { value: 80, label: '80 — 1080P' },
          { value: 74, label: '74 — 720P60（需 SESSDATA）' },
          { value: 64, label: '64 — 720P' },
          { value: 32, label: '32 — 480P' },
          { value: 16, label: '16 — 360P' }
        ]
      },
      {
        name: 'fnval',
        label: '格式',
        type: 'select',
        default: 1,
        options: [
          { value: 1, label: '1 — mp4 合一直链（durl）' },
          { value: 16, label: '16 — 仅 DASH（无直链）' },
          { value: 4048, label: '4048 — 全部 DASH（无直链）' }
        ]
      },
      { name: 'fourk', label: '允许 4K', type: 'bool', default: true },
      { name: 'sessdata', label: 'SESSDATA（高清晰度需要）', type: 'text', sensitive: true }
    ],
    buildCurl: (v) =>
      `curl -X POST "${BASE}/play-url" -H "Content-Type: application/json" -d '${JSON.stringify(v)}'`,
    submit: (v) => api.playUrl(v)
  },
  {
    id: 'danmaku',
    title: '分P弹幕',
    description: 'dm/list.so XML → 结构化列表（time 秒 / mode 类型 / text 内容）。cid 从「视频完整详情」的 pages[] 拿。',
    method: 'GET',
    path: '/api/bilibili-crawler/danmaku/{cid}',
    inputs: [{ name: 'cid', label: '分P cid', type: 'number', placeholder: '9001' }],
    buildCurl: (v) => `curl "${BASE}/danmaku/${v.cid ?? ''}"`,
    submit: (v) => api.danmaku(v.cid)
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
      {
        name: 'mode',
        label: '排序（透传上游）',
        type: 'select',
        default: 3,
        options: [
          { value: 3, label: '3 — 按热度' },
          { value: 2, label: '2 — 按时间' },
          { value: 0, label: '0 — 混合' },
          { value: 1, label: '1 — 混合' }
        ]
      },
      { name: 'sessdata', label: 'SESSDATA（可选，降风控）', type: 'text', sensitive: true }
    ],
    buildCurl: (v) =>
      `curl -X POST "${BASE}/comments" -H "Content-Type: application/json" -d '${JSON.stringify(v)}'`,
    submit: (v) => api.fetchComments(v)
  },
  {
    id: 'user-space',
    title: 'UP 主空间动态',
    description: '动态列表，抽取每条的 comment_id_str/comment_type（可直接喂给上面的两级评论）。注意：动态 feed 只是投稿的子集。',
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
  },
  {
    id: 'user-videos',
    title: 'UP 主全量投稿',
    description: 'WBI 签名的 arc/search——全部投稿（含非动态化、置顶隐藏的），抓「全部投稿的评论」场景用本端点拿 (aid, type=1) 对再喂两级评论。',
    method: 'POST',
    path: '/api/bilibili-crawler/user-videos',
    inputs: [
      { name: 'mid', label: 'UP 主 uid', type: 'text', placeholder: '42', default: '42' },
      { name: 'pn', label: '页码', type: 'number', default: 1 },
      { name: 'ps', label: '每页条数（≤50）', type: 'number', default: 30 },
      {
        name: 'order',
        label: '排序',
        type: 'select',
        default: 'pubdate',
        options: [
          { value: 'pubdate', label: 'pubdate — 最近发布' },
          { value: 'click', label: 'click — 最多播放' },
          { value: 'stow', label: 'stow — 最多收藏' }
        ]
      },
      { name: 'sessdata', label: 'SESSDATA（可选）', type: 'text', sensitive: true }
    ],
    buildCurl: (v) =>
      `curl -X POST "${BASE}/user-videos" -H "Content-Type: application/json" -d '${JSON.stringify(v)}'`,
    submit: (v) => api.fetchUserVideos(v)
  },
  {
    id: 'comments-archive',
    title: '评论归档下载（贪心翻页 → zip）',
    description: '与「两级评论」同管线，但忽略 pages：自动翻到上游 is_end 为止（安全上限 max_pages），服务端打包 zip 下载（README.md + comments.json + comments.md 可读渲染）。高频大评论区建议带 SESSDATA。',
    method: 'POST',
    path: '/api/bilibili-crawler/comments/archive',
    download: true,
    inputs: [
      { name: 'oid', label: 'oid（type=1 视频 aid；type=17 动态 id）', type: 'text', placeholder: '170001', default: '170001' },
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
      { name: 'include_replies', label: '展开楼中楼', type: 'bool', default: true },
      {
        name: 'mode',
        label: '排序（透传上游）',
        type: 'select',
        default: 3,
        options: [
          { value: 3, label: '3 — 按热度' },
          { value: 2, label: '2 — 按时间' }
        ]
      },
      { name: 'max_pages', label: '翻页安全上限（≤200）', type: 'number', default: 100 },
      { name: 'sessdata', label: 'SESSDATA（可选，降风控）', type: 'text', sensitive: true }
    ],
    buildCurl: (v) =>
      `curl -X POST "${BASE}/comments/archive" -H "Content-Type: application/json" -o comments.zip -d '${JSON.stringify(v)}'`,
    submit: (v) => api.commentsArchive(v)
  },
  {
    id: 'user-videos-archive',
    title: '投稿归档下载（贪心翻页 → zip）',
    description: '与「UP 主全量投稿」同管线，但自动翻 pn 到 count 覆盖完（安全上限 max_pn），服务端打包 zip 下载（README.md + videos.json + videos.md 表格）。',
    method: 'POST',
    path: '/api/bilibili-crawler/user-videos/archive',
    download: true,
    inputs: [
      { name: 'mid', label: 'UP 主 uid', type: 'text', placeholder: '42', default: '42' },
      { name: 'ps', label: '每页条数（≤50）', type: 'number', default: 30 },
      {
        name: 'order',
        label: '排序',
        type: 'select',
        default: 'pubdate',
        options: [
          { value: 'pubdate', label: 'pubdate — 最近发布' },
          { value: 'click', label: 'click — 最多播放' },
          { value: 'stow', label: 'stow — 最多收藏' }
        ]
      },
      { name: 'max_pn', label: '翻页安全上限（≤100）', type: 'number', default: 20 },
      { name: 'sessdata', label: 'SESSDATA（可选）', type: 'text', sensitive: true }
    ],
    buildCurl: (v) =>
      `curl -X POST "${BASE}/user-videos/archive" -H "Content-Type: application/json" -o videos.zip -d '${JSON.stringify(v)}'`,
    submit: (v) => api.userVideosArchive(v)
  }
]
