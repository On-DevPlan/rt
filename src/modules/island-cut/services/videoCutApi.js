/**
 * MP4 → 透明 GIF API client
 */

const API_BASE = '/api/island-cut/video'

/** 与后端 VideoCutParams 默认值保持一致 */
export const DEFAULT_PARAMS = {
  fps: 12,
  max_size: 360,
  bg_tol: 50,
  pad: 6,
  max_duration_sec: 60,
  max_frames: 600,
  max_output_kb: null  // 输出体积上限 KB；null = 不限制
}

/**
 * @param {File} file  MP4 视频
 * @param {object} params  VideoCutParams
 * @returns {Promise<{job_id, width, height, frame_count, src_fps, out_fps,
 *   duration_sec, elapsed_ms, gif_url, preview_url}>}
 */
export async function cutVideo(file, params) {
  const form = new FormData()
  form.append('file', file)
  // max_output_kb → 后端 max_output_bytes（KB → ×1024；null 不传）
  const { max_output_kb, ...rest } = params
  const payload = max_output_kb != null
    ? { ...rest, max_output_bytes: Math.round(max_output_kb * 1024) }
    : { ...rest, max_output_bytes: null }
  form.append('params', JSON.stringify(payload))

  const response = await fetch(`${API_BASE}/jobs`, { method: 'POST', body: form })

  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    const msg = typeof detail.detail === 'string'
      ? detail.detail
      : JSON.stringify(detail.detail)
    const err = new Error(msg || `Island video API error: ${response.status}`)
    err.status = response.status
    throw err
  }

  return response.json()
}

export const gifUrl = (jobId) => `${API_BASE}/jobs/${jobId}/gif`
export const previewUrl = (jobId) => `${API_BASE}/jobs/${jobId}/preview.png`