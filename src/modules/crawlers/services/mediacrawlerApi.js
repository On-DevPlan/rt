import { request } from './http.js'

const P = '/mediacrawler'

// GET /api/mediacrawler/platforms
export const platforms = () => request('GET', `${P}/platforms`)

// POST /api/mediacrawler/search  body: SearchRequest
export const searchBili = (req) => request('POST', `${P}/search`, { body: req })
