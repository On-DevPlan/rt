// 共享 HTTP 包装：非抛出风格，返回 { ok, status, data }（与 reversingApi 约定一致）。
// vite.config.js 已把 /api 反代到 127.0.0.1:8080，这里只管拼路径。

export const API_BASE = '/api'

export async function request(method, path, { body, query, headers } = {}) {
  const params = new URLSearchParams()
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== '') params.set(k, String(v))
    }
  }
  const qs = params.toString()
  const url = `${API_BASE}${path}${qs ? `?${qs}` : ''}`

  const res = await fetch(url, {
    method,
    headers: {
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...headers
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {})
  })

  let data = null
  try {
    data = await res.json()
  } catch {
    data = null
  }

  return { ok: res.ok, status: res.status, data }
}

// 二进制下载：返回 { ok, status, blob, filename }（filename 取 Content-Disposition）
export async function download(method, path, { body, query, headers } = {}) {
  const params = new URLSearchParams()
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== '') params.set(k, String(v))
    }
  }
  const qs = params.toString()
  const url = `${API_BASE}${path}${qs ? `?${qs}` : ''}`

  const res = await fetch(url, {
    method,
    headers: {
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...headers
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {})
  })

  if (!res.ok) {
    let data = null
    try {
      data = await res.json()
    } catch {
      data = null
    }
    return { ok: false, status: res.status, blob: null, filename: null, data }
  }

  const blob = await res.blob()
  const cd = res.headers.get('content-disposition') || ''
  const match = cd.match(/filename="?([^";]+)"?/)
  return { ok: true, status: res.status, blob, filename: match ? match[1] : 'download.bin' }
}
