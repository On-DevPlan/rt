import { download, request } from './http.js'

// POST /api/skill-seekers/scrape  body: ScrapeRequest
export const scrape = (req) => request('POST', '/skill-seekers/scrape', { body: req })

// POST /api/skill-seekers/scrape/archive  body: ArchiveScrapeRequest → zip blob
export const archive = (req) => download('POST', '/skill-seekers/scrape/archive', { body: req })
