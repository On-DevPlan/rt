/**
 * Tetris AI backend client.
 * Stateless: pass a board snapshot + the piece to place, get back where to put
 * it and the key sequence to get there.
 */

const API_BASE = '/api/tetris'

/**
 * @typedef {Object} NextMoveRequest
 * @property {string[][]} board  Top-down rows of "." or piece letters.
 * @property {string} piece      I / O / T / S / Z / J / L
 * @property {string} [next_piece]
 * @property {number} [current_x]
 * @property {number} [current_rotation]
 *
 * @typedef {Object} NextMoveResponse
 * @property {number} rotation
 * @property {number} target_x
 * @property {number} final_y
 * @property {string[]} moves
 * @property {number} score
 * @property {number} cleared_lines
 * @property {boolean} lookahead
 * @property {Object} metrics
 * @property {number} elapsed_ms
 */

/**
 * Ask the backend for the best placement of `piece` on `board`.
 * @param {NextMoveRequest} req
 * @returns {Promise<NextMoveResponse>}
 */
export async function fetchNextMove(req) {
  const response = await fetch(`${API_BASE}/next-move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req)
  })

  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    const err = new Error(detail.detail || `Tetris API error: ${response.status}`)
    err.status = response.status
    throw err
  }

  return response.json()
}
