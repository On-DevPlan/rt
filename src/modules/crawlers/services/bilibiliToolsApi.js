import { request } from './http.js'

const P = '/bilibili-tools'

// GET /api/bilibili-tools/favorites?link=|mid+fid&limit=
export const favorites = ({ link, mid, fid, limit }) =>
  request('GET', `${P}/favorites`, { query: { link, mid, fid, limit } })

// POST /api/bilibili-tools/favorites/add  body: AddFavoriteRequest（写操作）
export const addFavorites = (req) => request('POST', `${P}/favorites/add`, { body: req })

// GET /api/bilibili-tools/audio/{sid}?quality=
export const songInfo = (sid, { quality } = {}) =>
  request('GET', `${P}/audio/${encodeURIComponent(sid)}`, { query: { quality } })

// GET /api/bilibili-tools/audio/playlist/{sid}?max_pages=
export const playlistSongs = (sid, { max_pages } = {}) =>
  request('GET', `${P}/audio/playlist/${encodeURIComponent(sid)}`, { query: { max_pages } })

// GET /api/bilibili-tools/audio/user?uid=|link=&order=&max_pages=
export const userSongs = ({ uid, link, order, max_pages }) =>
  request('GET', `${P}/audio/user`, { query: { uid, link, order, max_pages } })
