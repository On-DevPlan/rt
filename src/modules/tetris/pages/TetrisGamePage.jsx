import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import styles from './TetrisGamePage.module.css'
import {
  COLS,
  ROWS,
  PIECES,
  boardToAscii,
  createBag,
  emptyBoard,
  hardDrop,
  lockPiece,
  pieceCells,
  spawnPiece,
  tryMove,
  tryRotate
} from '../utils/engine.js'
import { fetchNextMove } from '../services/tetrisApi.js'

const PIECE_COLORS = {
  I: '#5ad1ff',
  O: '#ffd14a',
  T: '#c66bff',
  S: '#58d97c',
  Z: '#ff6b6b',
  J: '#5b8cff',
  L: '#ff9d3d'
}

const EMPTY_DROP_INTERVAL = 800 // ms per row, level 0
const SOFT_DROP_INTERVAL = 50

function gravityStep(board, piece) {
  return tryMove(board, piece, 0, 1)
}

function applyMoves(board, piece, moves) {
  let p = piece
  for (const m of moves) {
    if (!p) return null
    if (m === 'rotate') p = tryRotate(board, p) || p
    else if (m === 'left') p = tryMove(board, p, -1, 0) || p
    else if (m === 'right') p = tryMove(board, p, 1, 0) || p
    else if (m === 'hard_drop') p = hardDrop(board, p)
    // 'soft_drop' ignored — caller handles it
  }
  return p
}

function pieceGhostCells(board, piece) {
  const dropped = hardDrop(board, piece)
  return pieceCells(dropped).map(([dx, dy]) => [dropped.x + dx, dropped.y + dy])
}

function buildOverlayCells(board, piece, hint) {
  if (!hint) return []
  // Walk the move sequence on a *copy* of the board (we won't actually lock it
  // because the player still has the controls). The result gives the
  // destination cells of the piece in the same coordinate system as `board`.
  const target = applyMoves(board, piece, hint.moves)
  if (!target) return []
  return pieceCells(target).map(([dx, dy]) => [target.x + dx, target.y + dy])
}

function buildFinalBoardWithPiece(board, piece) {
  // Returns a board where the currently falling piece is stamped as letters,
  // used for rendering before the user has hard-dropped it.
  const next = board.map((row) => row.slice())
  for (const [dx, dy] of pieceCells(piece)) {
    const x = piece.x + dx
    const y = piece.y + dy
    if (y < 0 || y >= ROWS || x < 0 || x >= COLS) continue
    next[y][x] = piece.type
  }
  return next
}

export default function TetrisGamePage() {
  const [board, setBoard] = useState(emptyBoard)
  const [piece, setPiece] = useState(null)
  const [nextQueue, setNextQueue] = useState(() => ['I', 'O'])
  const [score, setScore] = useState(0)
  const [lines, setLines] = useState(0)
  const [gameOver, setGameOver] = useState(false)
  // `hint` is the *last* successful response. We keep it across requests so the
  // side panel never unmounts; only its contents swap in. A fresh request bumps
  // `hintRequestId` and a transient `hintError` / `hintLoading` reflect status.
  const [hint, setHint] = useState(null)
  const [hintRequestId, setHintRequestId] = useState(0)
  const [hintError, setHintError] = useState(null)
  const [hintLoading, setHintLoading] = useState(false)
  const [autohint, setAutohint] = useState(true)
  const [showGhost, setShowGhost] = useState(true)
  const [elapsedMs, setElapsedMs] = useState(null)

  const bagRef = useRef(createBag())
  // Mirror of `nextQueue` so refreshHint can read it without depending on it
  // (which would otherwise rebuild the callback on every new piece).
  const nextQueueRef = useRef(['I', 'O'])
  const tickRef = useRef(null)
  const lastTickRef = useRef(0)
  const softDropRef = useRef(false)

  // ─── Piece lifecycle ───────────────────────────────────────────────────────

  const startNewPiece = useCallback((b) => {
    const type = bagRef.current.next()
    const p = spawnPiece(type)
    if (b && lockPiece(b, p).board === undefined) {
      // first frame: b is null
    }
    if (b) {
      // If the freshly spawned piece already collides, the player has topped out.
      // We approximate by checking collision against the *current* piece at y=0.
      const collidesNow = (() => {
        for (const [dx, dy] of pieceCells(p)) {
          const x = p.x + dx
          const y = p.y + dy
          if (y >= 0 && b[y][x]) return true
        }
        return false
      })()
      if (collidesNow) {
        setGameOver(true)
        return p
      }
    }
    return p
  }, [])

  // Initialize the first piece on mount.
  useEffect(() => {
    const first = startNewPiece(emptyBoard())
    setPiece(first)
    const queue = bagRef.current.peek(3)
    nextQueueRef.current = queue
    setNextQueue(queue)
    // We deliberately skip collision-check on the very first spawn by passing
    // an empty board; the next user-driven spawn will be checked properly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ─── Hint (AI) ────────────────────────────────────────────────────────────

  const refreshHint = useCallback(
    async (currentBoard, currentPiece) => {
      if (!currentPiece) return
      const reqId = hintRequestId + 1
      setHintRequestId(reqId)
      setHintLoading(true)
      setHintError(null)
      try {
        const result = await fetchNextMove({
          board: boardToAscii(currentBoard),
          piece: currentPiece.type,
          next_piece: nextQueueRef.current[0],
          current_x: currentPiece.x,
          current_rotation: currentPiece.rotation
        })
        // Guard against stale responses: only apply if no newer request fired.
        setHintRequestId((latest) => {
          if (latest === reqId) {
            setHint(result)
            setElapsedMs(result.elapsed_ms)
          }
          return latest
        })
      } catch (e) {
        setHintRequestId((latest) => {
          if (latest === reqId) {
            setHintError(e.status === 409 ? '棋盘已满，无可落点' : e.message)
          }
          return latest
        })
      } finally {
        setHintRequestId((latest) => {
          if (latest === reqId) setHintLoading(false)
          return latest
        })
      }
    },
    // Stable callback — reads nextQueue via ref, so the autohint effect doesn't
    // tear down and remount the side panel every time the queue advances.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  [])

  // Re-query the AI whenever a new piece is spawned (and autohint is on).
  useEffect(() => {
    if (!autohint || !piece || gameOver) return
    refreshHint(board, piece)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [piece, gameOver, autohint])

  // ─── Input handling ───────────────────────────────────────────────────────

  const move = useCallback(
    (dx) => {
      if (gameOver || !piece) return
      const next = tryMove(board, piece, dx, 0)
      if (next) setPiece(next)
    },
    [board, piece, gameOver]
  )

  const rotate = useCallback(() => {
    if (gameOver || !piece) return
    const next = tryRotate(board, piece)
    if (next) setPiece(next)
  }, [board, piece, gameOver])

  const softDrop = useCallback(() => {
    if (gameOver || !piece) return
    const next = gravityStep(board, piece)
    if (next) {
      setPiece(next)
      setScore((s) => s + 1)
    } else {
      // Lock immediately on soft-drop collision so the player feels response.
      lockAndAdvance(piece)
    }
  }, [board, piece, gameOver])

  const lockAndAdvance = useCallback(
    (p) => {
      const { board: after, lines: cleared } = lockPiece(board, p)
      setBoard(after)
      if (cleared > 0) {
        setLines((l) => l + cleared)
        setScore((s) => s + [0, 100, 300, 500, 800][cleared])
      }
      const fresh = startNewPiece(after)
      setPiece(fresh)
      const queue = bagRef.current.peek(3)
      nextQueueRef.current = queue
      setNextQueue(queue)
    },
    [board, startNewPiece]
  )

  const hardDropNow = useCallback(() => {
    if (gameOver || !piece) return
    const dropped = hardDrop(board, piece)
    setScore((s) => s + 2 * (ROWS - 1 - dropped.y))
    lockAndAdvance(dropped)
  }, [board, piece, gameOver, lockAndAdvance])

  const playHint = useCallback(() => {
    if (!hint || !piece) return
    const target = applyMoves(board, piece, hint.moves)
    if (!target) return
    setScore((s) => s + 2 * (ROWS - 1 - target.y))
    lockAndAdvance(target)
  }, [board, piece, hint, lockAndAdvance])

  useEffect(() => {
    function onKey(e) {
      if (e.repeat && e.code !== 'KeyA' && e.code !== 'KeyD' && e.code !== 'KeyS') return
      switch (e.code) {
        case 'KeyA':
        case 'ArrowLeft':
          e.preventDefault()
          move(-1)
          break
        case 'KeyD':
        case 'ArrowRight':
          e.preventDefault()
          move(1)
          break
        case 'KeyW':
        case 'ArrowUp':
          e.preventDefault()
          rotate()
          break
        case 'KeyS':
        case 'ArrowDown':
          e.preventDefault()
          softDropRef.current = true
          softDrop()
          break
        case 'Space':
          e.preventDefault()
          hardDropNow()
          break
        case 'KeyH':
          e.preventDefault()
          refreshHint(board, piece)
          break
        case 'KeyG':
          e.preventDefault()
          playHint()
          break
        default:
          break
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [move, rotate, softDrop, hardDropNow, refreshHint, playHint, board, piece])

  // ─── Gravity loop ─────────────────────────────────────────────────────────

  useEffect(() => {
    if (gameOver || !piece) return
    function step() {
      const now = performance.now()
      const interval = softDropRef.current ? SOFT_DROP_INTERVAL : EMPTY_DROP_INTERVAL
      softDropRef.current = false
      if (now - lastTickRef.current < interval) return
      lastTickRef.current = now
      const next = gravityStep(board, piece)
      if (next) {
        setPiece(next)
      } else {
        lockAndAdvance(piece)
      }
    }
    tickRef.current = setInterval(step, 16)
    return () => clearInterval(tickRef.current)
  }, [board, piece, gameOver, lockAndAdvance])

  // ─── Render ───────────────────────────────────────────────────────────────

  const display = useMemo(() => (piece ? buildFinalBoardWithPiece(board, piece) : board), [board, piece])
  const ghostCells = useMemo(
    () => (piece && showGhost ? pieceGhostCells(board, piece) : []),
    [board, piece, showGhost]
  )
  const ghostSet = useMemo(() => new Set(ghostCells.map(([x, y]) => `${x},${y}`)), [ghostCells])
  const hintCells = useMemo(() => (piece && hint ? buildOverlayCells(board, piece, hint) : []), [board, piece, hint])
  const hintSet = useMemo(() => new Set(hintCells.map(([x, y]) => `${x},${y}`)), [hintCells])

  const reset = () => {
    bagRef.current = createBag()
    setBoard(emptyBoard())
    const p = startNewPiece(emptyBoard())
    setPiece(p)
    const queue = bagRef.current.peek(3)
    nextQueueRef.current = queue
    setNextQueue(queue)
    setScore(0)
    setLines(0)
    setGameOver(false)
    setHint(null)
    setHintError(null)
    setElapsedMs(null)
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <h2 className={styles.title}>Tetris · 后端 AI 实时提示</h2>
          <p className={styles.subtitle}>
            方块控制：<kbd>A</kbd>/<kbd>D</kbd> 移动，<kbd>W</kbd> 旋转，<kbd>S</kbd> 软降，
            <kbd>Space</kbd> 硬降，<kbd>H</kbd> 刷新提示，<kbd>G</kbd> 一键执行提示
          </p>
        </div>
        <div className={styles.controls}>
          <label className={styles.toggle}>
            <input
              type="checkbox"
              checked={autohint}
              onChange={(e) => setAutohint(e.target.checked)}
            />
            实时提示
          </label>
          <label className={styles.toggle}>
            <input
              type="checkbox"
              checked={showGhost}
              onChange={(e) => setShowGhost(e.target.checked)}
            />
            阴影落点
          </label>
          <button type="button" className={styles.button} onClick={reset}>
            重新开始
          </button>
        </div>
      </header>

      <div className={styles.stage}>
        <div className={styles.boardFrame}>
          <div
            className={styles.board}
            style={{ gridTemplateColumns: `repeat(${COLS}, 1fr)` }}
          >
            {display.map((row, y) =>
              row.map((cell, x) => {
                const key = `${x},${y}`
                const isGhost = ghostSet.has(key) && !cell
                const isHint = hintSet.has(key) && !cell
                const cls = [
                  styles.cell,
                  cell && styles.filled,
                  isGhost && styles.ghost,
                  isHint && styles.hint,
                  cell && styles[`fill-${cell}`]
                ]
                  .filter(Boolean)
                  .join(' ')
                return <div key={key} className={cls} style={cell ? { '--piece-color': PIECE_COLORS[cell] } : undefined} />
              })
            )}
          </div>

          {gameOver && (
            <div className={styles.overlay}>
              <div className={styles.overlayCard}>
                <h3>游戏结束</h3>
                <p>得分 {score} · 消行 {lines}</p>
                <button type="button" className={styles.button} onClick={reset}>
                  再来一局
                </button>
              </div>
            </div>
          )}
        </div>

        <aside className={styles.sidePanel}>
          <section className="panel">
            <h3>本局数据</h3>
            <div className={styles.metrics}>
              <div>
                <span className="metric-value">{score}</span>
                <span className={styles.metricLabel}>得分</span>
              </div>
              <div>
                <span className="metric-value">{lines}</span>
                <span className={styles.metricLabel}>消行</span>
              </div>
              <div>
                <span className="metric-value">
                  {elapsedMs == null ? '—' : `${elapsedMs} ms`}
                </span>
                <span className={styles.metricLabel}>AI 耗时</span>
              </div>
            </div>
          </section>

          <section className="panel">
            <h3>下一块</h3>
            <div className={styles.nextList}>
              {nextQueue.map((t, i) => (
                <PiecePreview key={i} type={t} />
              ))}
            </div>
          </section>

          <section className="panel">
            <h3>AI 最佳落法</h3>
            {/* Always render the same DOM shape so the card frame never
                remounts. Empty / loading / error / hint are just style swaps
                on the same inner container. */}
            <div className={styles.hintBody}>
              {hintError ? (
                <p className={styles.errorText}>{hintError}</p>
              ) : hintLoading && !hint ? (
                <p className={styles.dimText}>计算中…</p>
              ) : hint ? (
                <>
                  <div className={styles.hintRow}>
                    <span className="tag">旋转</span>
                    <span className={styles.hintValue}>{hint.rotation}</span>
                    <span className="tag">x</span>
                    <span className={styles.hintValue}>{hint.target_x}</span>
                    {hintLoading && <span className={styles.dimText}> · 计算中…</span>}
                  </div>
                  <div className={styles.hintRow}>
                    <span className="tag">评分</span>
                    <span className={styles.hintValue}>{hint.score.toFixed(2)}</span>
                    <span className="tag">消行</span>
                    <span className={styles.hintValue}>{hint.cleared_lines}</span>
                  </div>
                  <ol className={styles.moveList}>
                    {hint.moves.map((m, i) => (
                      <li key={i}>{moveLabel(m)}</li>
                    ))}
                  </ol>
                  <button
                    type="button"
                    className={styles.button}
                    onClick={playHint}
                    disabled={hintLoading}
                  >
                    一键执行 (G)
                  </button>
                </>
              ) : (
                <p className={styles.dimText}>等待新方块…</p>
              )}
            </div>
          </section>

          <section className="tip-card">
            <p>
              蓝色方框 = AI 推荐的最终位置，灰色方块 = 阴影落点（无 AI 也会显示）。
              想关掉提示，关闭顶部"实时提示"开关。
            </p>
          </section>
        </aside>
      </div>
    </div>
  )
}

function moveLabel(m) {
  switch (m) {
    case 'rotate':
      return '旋转'
    case 'left':
      return '←'
    case 'right':
      return '→'
    case 'hard_drop':
      return '硬降'
    case 'soft_drop':
      return '软降'
    default:
      return m
  }
}

function PiecePreview({ type }) {
  const cells = PIECES[type][0]
  const w = cells.reduce((m, [x]) => Math.max(m, x), 0) + 1
  const h = cells.reduce((m, [, y]) => Math.max(m, y), 0) + 1
  const grid = Array.from({ length: h }, () => Array(w).fill(0))
  for (const [x, y] of cells) grid[y][x] = 1
  return (
    <div className={styles.preview}>
      {grid.map((row, y) =>
        row.map((c, x) => (
          <div
            key={`${x},${y}`}
            className={c ? `${styles.previewCell} ${styles[`fill-${type}`]}` : styles.previewEmpty}
            style={c ? { '--piece-color': PIECE_COLORS[type] } : undefined}
          />
        ))
      )}
    </div>
  )
}
