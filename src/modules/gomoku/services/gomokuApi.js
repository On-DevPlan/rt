/**
 * Stateless Gomoku AI client. One call per move.
 */

const API_BASE = '/api/gomoku'

/**
 * @param {number[][]} board  15x15 int matrix (0/1/2)
 * @param {1|2} toMove        side to play
 * @param {number} topK       number of candidate moves to return
 * @param {1|2|3} strength    AI strength tier: 1 弱 / 2 中 / 3 强
 * @returns {Promise<{best:{row,col,score,winning,blocks}, top_moves:Array, elapsed_ms:number}>}
 */
export async function fetchNextMove(board, toMove, topK = 3, strength = 2) {
  const response = await fetch(`${API_BASE}/next-move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ board, to_move: toMove, top_k: topK, strength })
  })

  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    const err = new Error(detail.detail || `Gomoku API error: ${response.status}`)
    err.status = response.status
    throw err
  }

  return response.json()
}
