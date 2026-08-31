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
  max_frames: 600,
  use_palette: false
}

/**
 * 压缩倍数 → APNG 模式映射（PNG 调色板离散切换 + fps 阶梯作精细控制）：
 *   1x  → palette=false (真 RGBA，零压缩)
 *   2x  → palette=true  (256 色调色板，约 1/3-1/4 体积)
 *   ≥3x → palette=true  (后续 max_output_bytes 自动 fps 阶梯)
 *
 * APNG 无 quality 滑杆（PNG 本质无损）；倍数 ≥2 走调色板，更大压缩靠 max_output_bytes。
 */
export function compressFactorToPalette(factor) {
  return factor >= 2
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