import { request } from './http.js'

const P = '/mediacrawler'

// GET /api/mediacrawler/platforms
export const platforms = () => request('GET', `${P}/platforms`)

// POST /api/mediacrawler/search  body: SearchRequest
export const searchBili = (req) => request('POST', `${P}/search`, { body: req })

import { download } from './http.js'

// POST /api/mediacrawler/search/archive → zip（贪心翻页）
export const searchArchive = (req) => download('POST', `${P}/search/archive`, { body: req })
