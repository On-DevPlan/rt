import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import styles from './GomokuPage.module.css'
import {
  BLACK,
  WHITE,
  EMPTY,
  SIZE,
  PLAYER_LABEL,
  cloneBoard,
  emptyBoard,
  isBoardFull,
  stoneCount,
  winningLine
} from '../utils/engine.js'
import { fetchNextMove } from '../services/gomokuApi.js'

const HUMAN_AI = 'human-ai'
const AI_AI = 'ai-ai'

export default function GomokuPage() {
  const [mode, setMode] = useState(HUMAN_AI)
  const [humanColor, setHumanColor] = useState(BLACK) // who the human plays in HUMAN_AI
  const [board, setBoard] = useState(emptyBoard)
  const [turn, setTurn] = useState(BLACK) // whose turn (BLACK moves first)
  const [status, setStatus] = useState('idle') // idle | playing | over
  const [winner, setWinner] = useState(EMPTY)
  const [winLine, setWinLine] = useState(null)
  const [lastMove, setLastMove] = useState(null)
  const [hint, setHint] = useState(null) // {row, col, score, top}
  const [aiThinking, setAiThinking] = useState(false)
  const [aiError, setAiError] = useState(null)
  const [autoPlay, setAutoPlay] = useState(true) // AI_AI running
  const [speed, setSpeed] = useState(500) // ms between AI_AI moves
  const [strength, setStrength] = useState(2) // 1 弱 / 2 中 / 3 强
  const [aiElapsedMs, setAiElapsedMs] = useState(null)

  // Mirrors for use inside async / timeout closures.
  const statusRef = useRef(status)
  useEffect(() => {
    statusRef.current = status
  }, [status])

  const aiColor = mode === HUMAN_AI ? 3 - humanColor : null

  // ─── placement ────────────────────────────────────────────────────────────

  const applyPlacement = useCallback((r, c, player) => {
    setBoard((prev) => {
      if (prev[r][c] !== EMPTY) return prev
      const next = cloneBoard(prev)
      next[r][c] = player
      const line = winningLine(next, r, c, player)
      if (line) {
        setStatus('over')
        setWinner(player)
        setWinLine(line)
      } else if (isBoardFull(next)) {
        setStatus('over')
        setWinner(EMPTY)
      } else {
        setTurn(3 - player)
      }
      return next
    })
    setLastMove([r, c])
    setHint(null)
  }, [])

  // ─── AI move (shared by HUMAN_AI reply and AI_AI loop) ────────────────────

  const runAiMove = useCallback(
    async (snapshotBoard, snapshotTurn) => {
      setAiThinking(true)
      setAiError(null)
      try {
        const result = await fetchNextMove(snapshotBoard, snapshotTurn, 3, strength)
        if (statusRef.current !== 'playing') return
        setAiElapsedMs(result.elapsed_ms)
        applyPlacement(result.best.row, result.best.col, snapshotTurn)
      } catch (e) {
        if (statusRef.current === 'playing') {
          setAiError(e.status === 409 ? '棋盘已满，无合法着点' : e.message)
        }
      } finally {
        setAiThinking(false)
      }
    },
    [applyPlacement, strength]
  )

  // Effect: when it's an AI's turn and the game is on, schedule a move.
  useEffect(() => {
    if (status !== 'playing' || aiThinking) return
    let aiTurn = false
    let delay = 0
    if (mode === AI_AI) {
      if (!autoPlay) return
      aiTurn = true
      delay = speed
    } else if (mode === HUMAN_AI && turn === aiColor) {
      aiTurn = true
      delay = 250
    }
    if (!aiTurn) return
    const snapshotBoard = board
    const snapshotTurn = turn
    const id = setTimeout(() => runAiMove(snapshotBoard, snapshotTurn), delay)
    return () => clearTimeout(id)
  }, [board, turn, status, mode, aiColor, autoPlay, speed, aiThinking, runAiMove])

  // ─── human interaction ────────────────────────────────────────────────────

  const onCellClick = (r, c) => {
    if (status !== 'playing') return
    if (mode !== HUMAN_AI) return // AI_AI: board is not clickable
    if (turn !== humanColor || aiThinking) return
    if (board[r][c] !== EMPTY) return
    applyPlacement(r, c, humanColor)
  }

  const askHint = async () => {
    if (status !== 'playing' || aiThinking) return
    if (mode !== HUMAN_AI || turn !== humanColor) return
    setAiThinking(true)
    setAiError(null)
    try {
      const result = await fetchNextMove(board, humanColor, 3, strength)
      if (statusRef.current !== 'playing') return
      setHint({
        row: result.best.row,
        col: result.best.col,
        score: result.best.score,
        top: result.top_moves
      })
      setAiElapsedMs(result.elapsed_ms)
    } catch (e) {
      setAiError(e.message)
    } finally {
      setAiThinking(false)
    }
  }

  const applyHint = () => {
    if (!hint) return
    applyPlacement(hint.row, hint.col, humanColor)
  }

  // ─── controls ─────────────────────────────────────────────────────────────

  const start = () => {
    setBoard(emptyBoard())
    setTurn(BLACK)
    setStatus('playing')
    setWinner(EMPTY)
    setWinLine(null)
    setLastMove(null)
    setHint(null)
    setAiError(null)
    setAiElapsedMs(null)
    setAutoPlay(true)
  }

  const reset = () => {
    setStatus('idle')
    setBoard(emptyBoard())
    setTurn(BLACK)
    setWinner(EMPTY)
    setWinLine(null)
    setLastMove(null)
    setHint(null)
    setAiError(null)
    setAutoPlay(true)
  }

  const changeMode = (m) => {
    setMode(m)
    reset()
  }

  // ─── derived ──────────────────────────────────────────────────────────────

  const moves = stoneCount(board)
  const winSet = useMemo(
    () => new Set((winLine || []).map(([r, c]) => `${r},${c}`)),
    [winLine]
  )
  const isHumanTurn =
    status === 'playing' && mode === HUMAN_AI && turn === humanColor && !aiThinking

  const statusText = (() => {
    if (status === 'idle') return '未开始'
    if (status === 'over') return winner === EMPTY ? '和棋（棋盘已满）' : `${PLAYER_LABEL[winner]} 胜`
    if (aiThinking) return `AI 思考中…`
    return `轮到 ${PLAYER_LABEL[turn]} 方`
  })()

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <h2 className={styles.title}>五子棋 · AI 对弈</h2>
          <p className={styles.subtitle}>
            人机对战（可选先手）、AI 自战、对局中向 AI 求最佳着点。后端无状态：每手实时请求。
          </p>
        </div>
      </header>

      <div className={styles.stage}>
        <div className={styles.boardWrap}>
          <div
            className={styles.board}
            style={{ gridTemplateColumns: `repeat(${SIZE}, 1fr)` }}
          >
            {board.map((row, r) =>
              row.map((cell, c) => {
                const key = `${r},${c}`
                const isLast = lastMove && lastMove[0] === r && lastMove[1] === c
                const isWin = winSet.has(key)
                const isHint = hint && hint.row === r && hint.col === c && cell === EMPTY
                const cellCls = [
                  styles.cell,
                  isLast && styles.last,
                  isWin && styles.win,
                  isHint && styles.hint
                ]
                  .filter(Boolean)
                  .join(' ')
                return (
                  <button
                    key={key}
                    type="button"
                    className={cellCls}
                    onClick={() => onCellClick(r, c)}
                    disabled={status !== 'playing' || cell !== EMPTY}
                  >
                    {cell === BLACK && <span className={`${styles.stone} ${styles.black}`} />}
                    {cell === WHITE && <span className={`${styles.stone} ${styles.white}`} />}
                    {isHint && <span className={styles.hintRing} />}
                    {isLast && cell !== EMPTY && <span className={styles.lastDot} />}
                  </button>
                )
              })
            )}
          </div>
        </div>

        <aside className={styles.side}>
          <section className="panel">
            <h3>对局模式</h3>
            <div className={styles.modeRow}>
              <button
                type="button"
                className={mode === HUMAN_AI ? `${styles.seg} ${styles.segActive}` : styles.seg}
                onClick={() => changeMode(HUMAN_AI)}
              >
                人机对战
              </button>
              <button
                type="button"
                className={mode === AI_AI ? `${styles.seg} ${styles.segActive}` : styles.seg}
                onClick={() => changeMode(AI_AI)}
              >
                AI 自战
              </button>
            </div>

            <div className={styles.field}>
              <label className={styles.fieldLabel}>AI 强度</label>
              <div className={styles.modeRow}>
                {[
                  { v: 1, label: '弱' },
                  { v: 2, label: '中' },
                  { v: 3, label: '强' }
                ].map((t) => (
                  <button
                    key={t.v}
                    type="button"
                    className={strength === t.v ? `${styles.seg} ${styles.segActive}` : styles.seg}
                    onClick={() => setStrength(t.v)}
                    title={
                      t.v === 1
                        ? '贪心静态，无前瞻（仍会堵四）'
                        : t.v === 2
                          ? '1 步前瞻，候选 beam=6'
                          : '1 步前瞻，候选 beam=12'
                    }
                  >
                    {t.label}
                  </button>
                ))}
              </div>
              <p className={styles.strengthHint}>
                {strength === 1 && '弱：只看一手强制战术（成五/堵四），其余贪心。'}
                {strength === 2 && '中：1 步前瞻，平衡速度与棋力。'}
                {strength === 3 && '强：更宽候选搜索，更易做形与双威胁。'}
              </p>
            </div>

            {mode === HUMAN_AI && (
              <div className={styles.field}>
                <label className={styles.fieldLabel}>我执（先手）</label>
                <div className={styles.modeRow}>
                  <button
                    type="button"
                    className={humanColor === BLACK ? `${styles.seg} ${styles.segActive}` : styles.seg}
                    onClick={() => {
                      setHumanColor(BLACK)
                      reset()
                    }}
                  >
                    黑（先手）
                  </button>
                  <button
                    type="button"
                    className={humanColor === WHITE ? `${styles.seg} ${styles.segActive}` : styles.seg}
                    onClick={() => {
                      setHumanColor(WHITE)
                      reset()
                    }}
                  >
                    白（后手）
                  </button>
                </div>
              </div>
            )}

            {mode === AI_AI && (
              <div className={styles.field}>
                <label className={styles.fieldLabel}>
                  节奏：{(speed / 1000).toFixed(2)}s / 手
                </label>
                <input
                  type="range"
                  min={100}
                  max={1500}
                  step={100}
                  value={speed}
                  onChange={(e) => setSpeed(Number(e.target.value))}
                  disabled={status !== 'playing'}
                />
              </div>
            )}

            <div className={styles.actionRow}>
              {status === 'idle' && (
                <button type="button" className={styles.primary} onClick={start}>
                  开始对局
                </button>
              )}
              {status === 'playing' && (
                <>
                  {mode === AI_AI && (
                    <button
                      type="button"
                      className={styles.button}
                      onClick={() => setAutoPlay((v) => !v)}
                    >
                      {autoPlay ? '暂停' : '继续'}
                    </button>
                  )}
                  <button type="button" className={styles.button} onClick={reset}>
                    认输 / 重开
                  </button>
                </>
              )}
              {status === 'over' && (
                <button type="button" className={styles.primary} onClick={start}>
                  再来一局
                </button>
              )}
            </div>
          </section>

          <section className="panel">
            <h3>局面</h3>
            <div className={styles.metrics}>
              <div>
                <span className="metric-value">{statusText}</span>
                <span className={styles.metricLabel}>状态</span>
              </div>
              <div>
                <span className="metric-value">{moves}</span>
                <span className={styles.metricLabel}>手数</span>
              </div>
              {aiElapsedMs != null && (
                <div>
                  <span className="metric-value">{aiElapsedMs} ms</span>
                  <span className={styles.metricLabel}>AI 耗时</span>
                </div>
              )}
            </div>
            {aiError && <p className={styles.errorText}>{aiError}</p>}
          </section>

          {mode === HUMAN_AI && (
            <section className="panel">
              <h3>AI 助攻</h3>
              <p className={styles.dimText}>
                对局中，轮到你时可让 AI 给出当前最佳着点（青色高亮），不会自动落子。
              </p>
              <div className={styles.actionRow}>
                <button
                  type="button"
                  className={styles.button}
                  onClick={askHint}
                  disabled={!isHumanTurn}
                >
                  求最佳着点 (H)
                </button>
                <button
                  type="button"
                  className={styles.button}
                  onClick={applyHint}
                  disabled={!isHumanTurn || !hint}
                >
                  执行建议 (G)
                </button>
              </div>
              {hint && (
                <div className={styles.hintInfo}>
                  <span className="tag">推荐</span>
                  <span>
                    ({hint.row}, {hint.col}) · 分 {hint.score}
                  </span>
                </div>
              )}
            </section>
          )}

          <section className="tip-card">
            <p>
              黑子先手。人机对战：点击棋盘落子；AI 自动应手。AI 自战：两边都由后端决策，
              可调节奏与暂停。规则为标准连五，无禁手。
            </p>
          </section>
        </aside>
      </div>

      {mode === HUMAN_AI && (
        <KeyHints onHint={askHint} onApply={applyHint} enabled={isHumanTurn} />
      )}
    </div>
  )
}

/** Keyboard shortcuts: H = ask hint, G = apply hint. */
function KeyHints({ onHint, onApply, enabled }) {
  useEffect(() => {
    function onKey(e) {
      if (!enabled) return
      if (e.code === 'KeyH') {
        e.preventDefault()
        onHint()
      } else if (e.code === 'KeyG') {
        e.preventDefault()
        onApply()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onHint, onApply, enabled])
  return null
}
