/**
 * Gomoku client-side engine.
 *
 * The backend (/api/gomoku/next-move) is stateless — it only returns a best
 * move for a given board. The client owns the game: turn bookkeeping, stone
 * placement, win detection. This module holds those pure helpers.
 *
 * Board: 15x15 int matrix, board[row][col], row 0 = top. 0 empty / 1 black / 2 white.
 */
export const SIZE = 15
export const BLACK = 1
export const WHITE = 2
export const EMPTY = 0
export const WIN_LEN = 5

const DIRS = [
  [1, 0], // vertical
  [0, 1], // horizontal
  [1, 1], // diagonal ↘
  [1, -1] // diagonal ↙
]

export function emptyBoard() {
  return Array.from({ length: SIZE }, () => Array(SIZE).fill(EMPTY))
}

export function cloneBoard(board) {
  return board.map((row) => row.slice())
}

export function inBounds(r, c) {
  return r >= 0 && r < SIZE && c >= 0 && c < SIZE
}

/**
 * Detect a 5-in-a-row through (r, c) for `player`. Returns the winning line
 * (array of [r, c]) or null.
 */
export function winningLine(board, r, c, player) {
  for (const [dr, dc] of DIRS) {
    const line = [[r, c]]
    let nr = r + dr
    let nc = c + dc
    while (inBounds(nr, nc) && board[nr][nc] === player) {
      line.push([nr, nc])
      nr += dr
      nc += dc
    }
    nr = r - dr
    nc = c - dc
    while (inBounds(nr, nc) && board[nr][nc] === player) {
      line.unshift([nr, nc])
      nr -= dr
      nc -= dc
    }
    if (line.length >= WIN_LEN) return line
  }
  return null
}

export function isBoardFull(board) {
  return board.every((row) => row.every((cell) => cell !== EMPTY))
}

export function stoneCount(board) {
  let n = 0
  for (const row of board) for (const cell of row) if (cell !== EMPTY) n++
  return n
}

export const PLAYER_LABEL = { [BLACK]: '黑', [WHITE]: '白' }
