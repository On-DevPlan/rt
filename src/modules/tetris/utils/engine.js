/**
 * Tetris game engine used by the page.
 *
 * Pure, framework-agnostic functions: board, pieces, gravity, collision, line
 * clears, and a deterministic 7-bag piece generator. Kept in its own file so
 * the page component stays focused on rendering and game-loop orchestration.
 *
 * Board coordinate convention matches the backend:
 * - rows[0] is the top of the board
 * - col 0 is the leftmost column
 * - empty cell = 0, occupied = the letter of the piece (e.g. "T", "I")
 */
export const COLS = 10
export const ROWS = 20

export const PIECE_TYPES = ['I', 'O', 'T', 'S', 'Z', 'J', 'L']

// Each piece has exactly four rotation states. Cells are [x, y] offsets from
// the piece's top-left bounding box, with min(x) == min(y) == 0.
export const PIECES = {
  I: [
    [[0, 0], [1, 0], [2, 0], [3, 0]],
    [[0, 0], [0, 1], [0, 2], [0, 3]],
    [[0, 0], [1, 0], [2, 0], [3, 0]],
    [[0, 0], [0, 1], [0, 2], [0, 3]]
  ],
  O: [
    [[0, 0], [1, 0], [0, 1], [1, 1]],
    [[0, 0], [1, 0], [0, 1], [1, 1]],
    [[0, 0], [1, 0], [0, 1], [1, 1]],
    [[0, 0], [1, 0], [0, 1], [1, 1]]
  ],
  T: [
    [[1, 0], [0, 1], [1, 1], [2, 1]],
    [[0, 0], [0, 1], [1, 1], [0, 2]],
    [[0, 0], [1, 0], [2, 0], [1, 1]],
    [[1, 0], [0, 1], [1, 1], [1, 2]]
  ],
  S: [
    [[1, 0], [2, 0], [0, 1], [1, 1]],
    [[0, 0], [0, 1], [1, 1], [1, 2]],
    [[1, 0], [2, 0], [0, 1], [1, 1]],
    [[0, 0], [0, 1], [1, 1], [1, 2]]
  ],
  Z: [
    [[0, 0], [1, 0], [1, 1], [2, 1]],
    [[1, 0], [0, 1], [1, 1], [0, 2]],
    [[0, 0], [1, 0], [1, 1], [2, 1]],
    [[1, 0], [0, 1], [1, 1], [0, 2]]
  ],
  J: [
    [[0, 0], [0, 1], [1, 1], [2, 1]],
    [[0, 0], [1, 0], [0, 1], [0, 2]],
    [[0, 0], [1, 0], [2, 0], [2, 1]],
    [[1, 0], [1, 1], [0, 2], [1, 2]]
  ],
  L: [
    [[2, 0], [0, 1], [1, 1], [2, 1]],
    [[0, 0], [0, 1], [0, 2], [1, 2]],
    [[0, 0], [1, 0], [2, 0], [0, 1]],
    [[0, 0], [1, 0], [1, 1], [1, 2]]
  ]
}

export function pieceWidth(type, rotation = 0) {
  const cells = PIECES[type][rotation]
  return cells.reduce((m, [x]) => Math.max(m, x), 0) + 1
}

export function pieceHeight(type, rotation = 0) {
  const cells = PIECES[type][rotation]
  return cells.reduce((m, [, y]) => Math.max(m, y), 0) + 1
}

export function emptyBoard() {
  return Array.from({ length: ROWS }, () => Array(COLS).fill(0))
}

// 7-bag generator: shuffle the seven pieces and yield them one by one, then
// reshuffle. Standard modern Tetris randomness.
export function createBag() {
  let queue = []
  const refill = () => {
    queue = [...PIECE_TYPES]
    for (let i = queue.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1))
      ;[queue[i], queue[j]] = [queue[j], queue[i]]
    }
  }
  refill()
  return {
    next() {
      if (queue.length === 0) refill()
      return queue.shift()
    },
    peek(n = 1) {
      let out = []
      let q = [...queue]
      let i = 0
      while (out.length < n) {
        if (q.length === 0) {
          q = [...PIECE_TYPES]
          for (let k = q.length - 1; k > 0; k--) {
            const j = Math.floor(Math.random() * (k + 1))
            ;[q[k], q[j]] = [q[j], q[k]]
          }
        }
        out.push(q.shift())
        i++
      }
      return out
    }
  }
}

export function spawnPiece(type) {
  const cells = PIECES[type][0]
  const w = cells.reduce((m, [x]) => Math.max(m, x), 0) + 1
  return {
    type,
    rotation: 0,
    x: Math.floor((COLS - w) / 2),
    y: 0
  }
}

export function pieceCells(piece) {
  return PIECES[piece.type][piece.rotation]
}

export function collides(board, piece) {
  const cells = pieceCells(piece)
  for (const [dx, dy] of cells) {
    const x = piece.x + dx
    const y = piece.y + dy
    if (x < 0 || x >= COLS || y >= ROWS) return true
    if (y >= 0 && board[y][x]) return true
  }
  return false
}

export function tryMove(board, piece, dx, dy) {
  const moved = { ...piece, x: piece.x + dx, y: piece.y + dy }
  if (collides(board, moved)) return null
  return moved
}

export function tryRotate(board, piece) {
  const next = { ...piece, rotation: (piece.rotation + 1) % 4 }
  // SRS-lite wall kicks: try the rotation, then nudges if it fails.
  const kicks = [0, -1, 1, -2, 2]
  for (const k of kicks) {
    const kicked = { ...next, x: next.x + k }
    if (!collides(board, kicked)) return kicked
  }
  return null
}

export function hardDrop(board, piece) {
  let p = piece
  while (true) {
    const next = { ...p, y: p.y + 1 }
    if (collides(board, next)) break
    p = next
  }
  return p
}

// Returns { board, lines } where `lines` is the count of rows just cleared.
export function lockPiece(board, piece) {
  const next = board.map((row) => row.slice())
  for (const [dx, dy] of pieceCells(piece)) {
    const x = piece.x + dx
    const y = piece.y + dy
    if (y < 0) continue // piece still spawning -> ignored
    next[y][x] = piece.type
  }
  // Remove full rows.
  const kept = next.filter((row) => row.some((c) => c === 0))
  const cleared = ROWS - kept.length
  const empty = Array.from({ length: cleared }, () => Array(COLS).fill(0))
  return { board: [...empty, ...kept], lines: cleared }
}

// Board to a 2D array of '.' and piece letters for the backend API.
export function boardToAscii(board) {
  return board.map((row) => row.map((c) => c || '.').join(''))
}
