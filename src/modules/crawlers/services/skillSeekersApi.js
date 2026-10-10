import { request } from './http.js'

// POST /api/skill-seekers/scrape  body: ScrapeRequest
export const scrape = (req) => request('POST', '/skill-seekers/scrape', { body: req })
