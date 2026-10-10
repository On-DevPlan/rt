import { request } from './http.js'

const P = '/bilibili-crawler'

// GET /api/bilibili-crawler/convert?aid=|bvid=
export const convert = ({ aid, bvid }) =>
  request('GET', `${P}/convert`, { query: { aid, bvid } })

// POST /api/bilibili-crawler/wbi/sign  body: { params: {...} }
export const wbiSign = (params) => request('POST', `${P}/wbi/sign`, { body: { params } })

// GET /api/bilibili-crawler/video/{video_id}（aid 或 bvid 自适应）?sessdata=
export const videoInfo = (videoId, { sessdata } = {}) =>
  request('GET', `${P}/video/${encodeURIComponent(videoId)}`, { query: { sessdata } })

// POST /api/bilibili-crawler/play-url  body: PlayUrlRequest（WBI 签名 playurl）
export const playUrl = (req) => request('POST', `${P}/play-url`, { body: req })

// GET /api/bilibili-crawler/danmaku/{cid}
export const danmaku = (cid) => request('GET', `${P}/danmaku/${encodeURIComponent(cid)}`)

// POST /api/bilibili-crawler/comments  body: CommentsRequest
export const fetchComments = (req) => request('POST', `${P}/comments`, { body: req })

// POST /api/bilibili-crawler/user-space  body: UserSpaceRequest
export const fetchUserSpace = (req) => request('POST', `${P}/user-space`, { body: req })

// POST /api/bilibili-crawler/user-videos  body: UserVideosRequest（WBI 签名的 arc/search）
export const fetchUserVideos = (req) => request('POST', `${P}/user-videos`, { body: req })
