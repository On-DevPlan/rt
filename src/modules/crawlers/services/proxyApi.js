import { request } from './http.js'

// GET /api/proxy/status?check_ip=true
export const status = ({ check_ip = true } = {}) =>
  request('GET', '/proxy/status', { query: { check_ip } })

// PUT /api/proxy/subscription  body: { url }
export const setSubscription = (url) => request('PUT', '/proxy/subscription', { body: { url } })

// DELETE /api/proxy/subscription（清除订阅、关闭代理、复位 stub 配置）
export const clearSubscription = () => request('DELETE', '/proxy/subscription')

// POST /api/proxy/toggle  body: { enabled }
export const toggle = (enabled) => request('POST', '/proxy/toggle', { body: { enabled } })

// POST /api/proxy/refresh（用已存 URL 重拉订阅）
export const refresh = () => request('POST', '/proxy/refresh')

// PUT /api/proxy/allowlist  body: { modules: [...] }
export const setAllowlist = (modules) => request('PUT', '/proxy/allowlist', { body: { modules } })
