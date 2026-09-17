/*!
 * hb-node-harness — 终章骨架（Node 侧）
 *
 * 这是给你抄的起点，不是答案。里面的 TODO 都得你自己填。
 *
 * 用法：
 *   1. 把 hb-crypto.js 和这个文件放到同一个目录
 *   2. 改下面的 BASE 指向你部署的地址
 *   3. node hb-node-harness.js
 *
 * 缺什么补什么——第 6 关教过你这件事。
 */
'use strict'

const BASE = process.env.HB_BASE || 'http://127.0.0.1:81'

// 把 hb-crypto.js 拿来用。它挂到 globalThis.HB 上。
require('./hb-crypto.js')
const C = globalThis.HB.crypto

// ---------------------------------------------------------------- 你手上的碎片

// 前 8 个碎片按顺序填进来（页面上的"碎片"区可以逐个复制）
const SHARDS = [
  '', // S0
  '', // S1
  '', // S2
  '', // S3
  '', // S4
  '', // S5
  '', // S6
  ''  // S7
]

const K4 = C.sha256(SHARDS[0] + SHARDS[1] + SHARDS[2] + SHARDS[3])
const K6 = C.sha256(SHARDS[6])
const K8 = C.sha256(SHARDS[7])
const K = C.sha256(SHARDS.join(''))

// ---------------------------------------------------------------- 第 7 关：UA 硬门

async function notarize() {
  const ts = Math.floor(Date.now() / 1000)
  const client = 'hb-node/1.0'
  const sig = C.hmac(K6, `${ts}|${client}`)

  const res = await fetch(`${BASE}/api/reversing/v1/notarize`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      // TODO: 这一行是第 7 关的全部。填对了才过得去。
      'User-Agent': ''
    },
    body: JSON.stringify({ ts, client, sig })
  })

  const body = await res.json()
  if (!res.ok) {
    console.error('[notarize] 被拒:', body)
    return null
  }

  // TODO: 用 K6 解出 S7
  return C.decrypt(K6, body.ct)
}

// ---------------------------------------------------------------- 第 8 关：PoW + 全协议

function leadingZeroBits(hex) {
  let bits = 0
  for (const ch of hex) {
    const n = parseInt(ch, 16)
    if (n === 0) { bits += 4; continue }
    bits += Math.clz32(n) - 28
    break
  }
  return bits
}

function solvePow(challenge, bits) {
  // TODO: 找一个 nonce，使 sha256(`${challenge}:${nonce}`) 的前 bits 位是 0
  for (let nonce = 0; ; nonce++) {
    if (leadingZeroBits(C.sha256(`${challenge}:${nonce}`)) >= bits) {
      return nonce
    }
  }
}

async function terminal() {
  const chRes = await fetch(`${BASE}/api/reversing/v1/challenge`)
  const { challenge, bits, window } = await chRes.json()

  console.log(`[pow] challenge=${challenge} bits=${bits}`)
  const t0 = Date.now()
  const nonce = solvePow(challenge, bits)
  console.log(`[pow] nonce=${nonce} 用了 ${Date.now() - t0}ms`)

  const ts = Math.floor(Date.now() / 1000)
  const client = 'hb-node/1.0'
  const sig = C.hmac(K8, `${ts}|${window}|${nonce}`)

  const res = await fetch(`${BASE}/api/reversing/v1/terminal`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'hb-client/1.0'
    },
    body: JSON.stringify({ ts, window, nonce, client, sig })
  })

  const body = await res.json()
  if (!res.ok) {
    console.error('[terminal] 被拒:', body)
    return null
  }
  return body.ct
}

// ---------------------------------------------------------------- main

;(async () => {
  if (SHARDS.some((s) => !s)) {
    console.error('碎片没填全。先把 8 个碎片都收集到再跑。')
    process.exit(1)
  }

  const s7 = await notarize()
  if (s7) console.log('[gate-7] S7 =', s7)

  const blob = await terminal()
  if (blob) {
    console.log('[gate-8] final.blob =', blob)
    console.log('[gate-8] 明文 =', C.decrypt(K, blob))
  }
})()
