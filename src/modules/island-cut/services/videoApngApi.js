/**
 * MP4 → 透明 Animated PNG (APNG) API client
 */

const API_BASE = '/api/island-cut/video-apng'

export const DEFAULT_PARAMS = {
  fps: 12,
  max_size: 360,
  bg_tol: 50,
  pad: 6,
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
    const err = new Error(msg || `Island video APNG API error: ${response.status}`)
    err.status = response.status
    throw err
  }

  return response.json()
}

export const apngUrl = (jobId) => `${API_BASE}/jobs/${jobId}/apng`
export const previewUrl = (jobId) => `${API_BASE}/jobs/${jobId}/preview.png`