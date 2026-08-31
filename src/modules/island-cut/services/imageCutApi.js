/**
 * Island cut API client — upload an image, get transparent PNG pieces.
 */

const API_BASE = '/api/island-cut'

/** 与后端 schemas.CutParams 默认值保持一致 */
export const DEFAULT_PARAMS = {
  mode: 'auto',
  bg_threshold: 235,
  alpha_threshold: 0,
  closing_iters: 2,
  min_area: 1000,
  padding: 20,
  small_min_area: 12,
  connectivity: 8
}

/**
 * @param {File} file  上传的图片
 * @param {object} params  CutParams
 * @returns {Promise<{job_id:string, mode:string, width:number, height:number,
 *   elapsed_ms:number, piece_count:number, pieces:Array, zip_url:string, full_url:string}>}
 */
export async function cutImage(file, params) {
  const form = new FormData()
  form.append('file', file)
  form.append('params', JSON.stringify(params))

  const response = await fetch(`${API_BASE}/jobs`, { method: 'POST', body: form })

  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    const msg = typeof detail.detail === 'string'
      ? detail.detail
      : JSON.stringify(detail.detail)
    const err = new Error(msg || `Island cut API error: ${response.status}`)
    err.status = response.status
    throw err
  }

  return response.json()
}

export const pieceUrl = (jobId, filename) => `${API_BASE}/jobs/${jobId}/pieces/${filename}`
export const fullUrl = (jobId) => `${API_BASE}/jobs/${jobId}/full.png`
export const zipUrl = (jobId) => `${API_BASE}/jobs/${jobId}/zip`
