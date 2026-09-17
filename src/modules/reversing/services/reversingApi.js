/**
 * /api/reversing/v1 的客户端封装。
 *
 * 注意：这个文件会被打包进 React 壳，也就是会被压缩成天书。
 * 玩家想看懂壳自己的协议实现会很痛苦——这正是通往"自己写客户端"的推力。
 * 谜题本体在 public/reversing/js/ 下，是裸的。
 */

export const API_BASE = '/api/reversing/v1'

async function request(method, path, { body, headers } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...headers
    },
    ...(body ? { body: JSON.stringify(body) } : {})
  })

  let data = null
  try {
    data = await res.json()
  } catch {
    data = null
  }

  return { ok: res.ok, status: res.status, data }
}

export function getChallenge() {
  return request('GET', '/challenge')
}

export function handshake(payload) {
  return request('POST', '/handshake', { body: payload })
}

export function attest(payload) {
  return request('POST', '/attest', { body: payload })
}

export function notarize(payload, extraHeaders) {
  return request('POST', '/notarize', { body: payload, headers: extraHeaders })
}

export function terminal(payload) {
  return request('POST', '/terminal', { body: payload })
}

export function randomNonce() {
  // 非安全上下文下 crypto.getRandomValues 仍然可用（它不受安全上下文限制）
  const buf = new Uint8Array(8)
  crypto.getRandomValues(buf)
  return Array.from(buf, (b) => b.toString(16).padStart(2, '0')).join('')
}
