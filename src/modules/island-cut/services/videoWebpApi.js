/**
 * MP4 → 透明 Animated WebP API client
 */

const API_BASE = '/api/island-cut/video-webp'

/** 与后端 VideoCutParams 默认值一致 */
export const DEFAULT_PARAMS = {
  fps: 12,
  max_size: 360,
  bg_tol: 50,
  pad: 6,
  max_duration_sec: 60,
  max_frames: 600,
  quality: 80
}

/**
 * 压缩倍数 → WebP quality 映射（指数曲线，匹配经验上每档约 1.5-2× 缩小）：
 *   1x  → 100 (lossless，零压缩)
 *   2x  → 92
 *   4x  → 80  (推荐起点)
 *   8x  → 60
 *   16x → 32
 *   20x → 22
 */
export function compressFactorToQuality(factor) {
  const table = [
    [1, 100], [2, 92], [4, 80], [8, 60], [16, 32], [20, 22],
  ]
  if (factor <= 1) return 100
  if (factor >= 20) return 22
  for (let i = 0; i < table.length - 1; i++) {
    const [f1, q1] = table[i]
    const [f2, q2] = table[i + 1]
    if (factor >= f1 && factor <= f2) {
      const t = (factor - f1) / (f2 - f1)
      return Math.round(q1 + t * (q2 - q1))
    }
  }
  return 80
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
    const err = new Error(msg || `Island video WebP API error: ${response.status}`)
    err.status = response.status
    throw err
  }

  return response.json()
}

export const webpUrl = (jobId) => `${API_BASE}/jobs/${jobId}/webp`
export const previewUrl = (jobId) => `${API_BASE}/jobs/${jobId}/preview.png`