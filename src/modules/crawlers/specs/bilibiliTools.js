import * as api from '../services/bilibiliToolsApi.js'

const BASE = 'http://127.0.0.1:8080/api/bilibili-tools'

export const bilibiliToolsEndpoints = [
  {
    id: 'favorites',
    title: '收藏夹枚举',
    description: 'v3 接口枚举收藏夹内容（ps≤20 分页，按 has_more 停止）。link 或 mid+fid 二选一，link 优先。state=1 为失效视频。',
    method: 'GET',
    path: '/api/bilibili-tools/favorites',
    inputs: [
      { name: 'link', label: '收藏夹链接（优先）', type: 'text', placeholder: 'https://space.bilibili.com/42/favlist?fid=12345' },
      { name: 'mid', label: 'UP 主 uid（与 fid 一起）', type: 'text', placeholder: '42' },
      { name: 'fid', label: '收藏夹 fid', type: 'text', placeholder: '12345' },
      { name: 'limit', label: '条数上限（≤200）', type: 'number', default: 20 }
    ],
    buildCurl: (v) => {
      const q = new URLSearchParams()
      for (const k of ['link', 'mid', 'fid', 'limit']) {
        if (v[k] !== undefined && v[k] !== '') q.set(k, v[k])
      }
      return `curl "${BASE}/favorites?${q}"`
    },
    submit: (v) => api.favorites(v)
  },
  {
    id: 'favorites-add',
    title: '批量添加收藏（写操作 ⚠️）',
    description: '把多个 av 号加入指定收藏夹。需要 SESSDATA + bili_jct（csrf）。逐个返回结果：0=成功，11007/11201=已收藏，10003=稿件不存在。生产环境务必置于鉴权层后。',
    method: 'POST',
    path: '/api/bilibili-tools/favorites/add',
    inputs: [
      { name: 'sessdata', label: 'SESSDATA', type: 'text', sensitive: true },
      { name: 'bili_jct', label: 'bili_jct（csrf）', type: 'text', sensitive: true },
      { name: 'fid', label: '目标收藏夹 fid', type: 'text', placeholder: '12345' },
      { name: 'aids', label: 'av 号列表（每行一个，≤100）', type: 'list', placeholder: '170001\n2' }
    ],
    buildCurl: (v) =>
      `curl -X POST "${BASE}/favorites/add" -H "Content-Type: application/json" -d '${JSON.stringify(v)}'`,
    submit: (v) => api.addFavorites(v)
  },
  {
    id: 'song-info',
    title: '音频区 · 单曲信息 + CDN 直链',
    description: '歌曲信息（标题/作者/歌词/封面）+ 播放 CDN 直链。支持传 au{id} 完整链接或纯数字。cdns 带时效与 Referer 校验，下载需带 B 站 Referer。',
    method: 'GET',
    path: '/api/bilibili-tools/audio/{sid}',
    inputs: [
      { name: 'sid', label: '歌曲 id（au241921 或 241921）', type: 'text', placeholder: 'au241921', default: 'au241921' },
      {
        name: 'quality',
        label: '音质',
        type: 'select',
        default: 2,
        options: [
          { value: 0, label: '0 — 低' },
          { value: 1, label: '1 — 中' },
          { value: 2, label: '2 — 高' }
        ]
      }
    ],
    buildCurl: (v) => `curl "${BASE}/audio/${encodeURIComponent(v.sid)}?quality=${v.quality ?? 2}"`,
    submit: (v) => api.songInfo(v.sid, { quality: v.quality })
  },
  {
    id: 'menu-songs',
    title: '音频区 · 歌单歌曲',
    description: '歌单（am{id}）内全部歌曲列表，按 pageCount==curPage 停止翻页。',
    method: 'GET',
    path: '/api/bilibili-tools/audio/playlist/{sid}',
    inputs: [
      { name: 'sid', label: '歌单 id（am76105 或 76105）', type: 'text', placeholder: 'am76105', default: 'am76105' },
      { name: 'max_pages', label: '翻页上限（≤10）', type: 'number', default: 3 }
    ],
    buildCurl: (v) => `curl "${BASE}/audio/playlist/${encodeURIComponent(v.sid)}?max_pages=${v.max_pages ?? 3}"`,
    submit: (v) => api.playlistSongs(v.sid, { max_pages: v.max_pages })
  },
  {
    id: 'user-songs',
    title: '音频区 · UP 主歌曲',
    description: 'UP 主上传的歌曲列表。uid 或 link（space 链接）二选一。',
    method: 'GET',
    path: '/api/bilibili-tools/audio/user',
    inputs: [
      { name: 'uid', label: '数字 uid', type: 'text', placeholder: '2932528' },
      { name: 'link', label: 'space 链接（优先）', type: 'text', placeholder: 'https://space.bilibili.com/2932528/audio' },
      {
        name: 'order',
        label: '排序',
        type: 'select',
        default: 1,
        options: [
          { value: 1, label: '1 — 默认' },
          { value: 2, label: '2 — 其他' }
        ]
      },
      { name: 'max_pages', label: '翻页上限（≤10）', type: 'number', default: 3 }
    ],
    buildCurl: (v) => {
      const q = new URLSearchParams()
      for (const k of ['uid', 'link', 'order', 'max_pages']) {
        if (v[k] !== undefined && v[k] !== '') q.set(k, v[k])
      }
      return `curl "${BASE}/audio/user?${q}"`
    },
    submit: (v) => api.userSongs(v)
  }
]
