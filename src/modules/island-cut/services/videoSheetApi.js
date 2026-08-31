/**
 * MP4 → sprite sheet +帧 API client
 */

const API_BASE = '/api/island-cut/video-sheet'

export const DEFAULT_PARAMS = {
  fps: 12,
  tol: 35,
  min_area: 200,
  max_duration_sec: 60,
  max_frames: 600
}

export async function cutVideo(file, params) {
  const form = new FormData()
  form.append('file', file)
  form.append('params', JSON.stringify(params))

  const response = await fetch(`${API_BASE}/jobs`, { method: 'POST', body: form })

  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    const msg = typeof detail.detail === 'string'
      ? detail.detail
      : JSON.stringify(detail.detail)
    const err = new Error(msg || `Island video sheet API error: ${response.status}`)
    err.status = response.status
    throw err
  }

  return response.json()
}

export const sheetUrl = (jobId) => `${API_BASE}/jobs/${jobId}/sheet.png`
export const framesZipUrl = (jobId) => `${API_BASE}/jobs/${jobId}/frames.zip`
export const framesJsonUrl = (jobId) => `${API_BASE}/jobs/${jobId}/frames.json`
export const previewApngUrl = (jobId) => `${API_BASE}/jobs/${jobId}/preview.apng`
export const previewWebpUrl = (jobId) => `${API_BASE}/jobs/${jobId}/preview.webp`
export const bundleZipUrl = (jobId) => `${API_BASE}/jobs/${jobId}/bundle.zip`
export const singleFrameUrl = (jobId, filename) => `${API_BASE}/jobs/${jobId}/frames/${filename}`