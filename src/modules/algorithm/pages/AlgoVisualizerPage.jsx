import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useDocumentTitle } from '../../../framework/hooks/useDocumentTitle.js'
import styles from './AlgoVisualizerPage.module.css'

// ─── Inline Markdown Renderer ────────────────────────────────────────────────

function mdToHtml(text) {
  if (!text) return ''
  // Escape HTML first
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // Code blocks (```...```)
  html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>')

  // Inline code `...`
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')

  // Bold **...**
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')

  // Tables
  html = html.replace(/\n\|(.+)\|\n\|([-| ]+)\|\n((?:\n\|.+\|\n?)*)/g, (_, header, sep, rows) => {
    const headers = header.split('|').map(h => h.trim()).filter(Boolean)
    const aligns = sep.split('|').map(a => a.includes(':') ? (a.startsWith(':') && a.endsWith(':') ? 'center' : a.startsWith(':') ? 'left' : 'right') : null)
    let table = '<table><thead><tr>'
    headers.forEach((h, i) => table += `<th${aligns[i] ? ` align="${aligns[i]}"` : ''}>${h}</th>`)
    table += '</tr></thead><tbody>'
    rows.trim().split('\n').forEach(r => {
      const cells = r.split('|').filter((_, i, a) => i > 0 && i < a.length - 1).map(c => c.trim())
      table += '<tr>' + cells.map(c => `<td>${c}</td>`).join('') + '</tr>'
    })
    return table + '</tbody></table>'
  })

  // Blockquote >
  html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')

  // Unordered list items
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')

  // Line breaks
  html = html.replace(/\n\n/g, '</p><p>')
  html = html.replace(/\n/g, '<br>')

  return `<p>${html}</p>`
}

// ─── Algorithm Data ──────────────────────────────────────────────────────────

import algoData from '../data/two-sum.json'
import algoIndex from '../data/index.json'

// ─── Visualization Components ────────────────────────────────────────────────

function ArrayVisualizer({ state, currentIndex, highlightedIndices }) {
  const nums = state ? state.replace(/[\[\]]/g, '').split(', ').map(Number) : []
  const hl = highlightedIndices || []
  const ci = currentIndex ?? -1

  return (
    <div className={styles.arrayViz}>
      <div className={styles.vizLabel}>数组 nums</div>
      <div className={styles.arrayBoxes}>
        {nums.map((val, i) => {
          let cls = styles.arrayBox
          if (i === ci) cls += ` ${styles.current}`
          if (hl.includes(i)) cls += ` ${styles.highlighted}`
          return (
            <div key={i} className={cls} style={{ '--idx': i }}>
              <span className={styles.arrayValue}>{val}</span>
              <span className={styles.arrayIndex}>{i}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function MapVisualizer({ mapContents }) {
  if (!mapContents || mapContents === '{}') {
    return (
      <div className={styles.mapViz}>
        <div className={styles.vizLabel}>哈希表 Map</div>
        <div className={styles.mapEmpty}>∅ 空</div>
      </div>
    )
  }

  // Parse "{2 → 0, 7 → 1}" format
  const entries = mapContents
    .replace(/[{}]/g, '')
    .split(', ')
    .filter(Boolean)
    .map(pair => {
      const [k, v] = pair.split(' → ')
      return { key: k, value: v }
    })

  return (
    <div className={styles.mapViz}>
      <div className={styles.vizLabel}>哈希表 Map</div>
      <table className={styles.mapTable}>
        <thead>
          <tr>
            <th>Key (值)</th>
            <th>Value (索引)</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e, i) => (
            <tr key={i} className={styles.mapRow} style={{ '--row': i }}>
              <td className={styles.mapKey}>{e.key}</td>
              <td className={styles.mapVal}>{e.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ResultVisualizer({ result, highlightedIndices }) {
  const indices = result ? result.replace(/[\[\]]/g, '').split(', ').map(Number) : []

  return (
    <div className={styles.resultViz}>
      <div className={styles.vizLabel}>结果</div>
      <div className={styles.resultBadge}>
        <span className={styles.resultArrow}>→</span>
        <span className={styles.resultValue}>[{indices.join(', ')}]</span>
      </div>
      {highlightedIndices && highlightedIndices.length === 2 && (
        <div className={styles.resultExplanation}>
          nums[{highlightedIndices[0]}] + nums[{highlightedIndices[1]}] = 9
        </div>
      )}
    </div>
  )
}

// ─── Line Diff Engine ────────────────────────────────────────────────────────

/**
 * Compute a simple line diff between two code strings.
 * Returns diff entries: { type: 'same'|'add'|'del', text: string }
 * Uses common-prefix/suffix detection — works well for sequential code building.
 */
function computeLineDiff(prevCode, currentCode) {
  const prevLines = (prevCode || '').split('\n')
  const currLines = currentCode.split('\n')
  const result = []
  const minLen = Math.min(prevLines.length, currLines.length)

  // 1. Common prefix
  let i = 0
  while (i < minLen && prevLines[i] === currLines[i]) {
    result.push({ type: 'same', text: prevLines[i] })
    i++
  }

  // 2. Find common suffix (from end inward)
  let p = prevLines.length - 1
  let c = currLines.length - 1
  while (p >= i && c >= i && prevLines[p] === currLines[c]) {
    p--
    c--
  }

  // 3. Removed lines (between prefix and suffix in old)
  for (let j = i; j <= p; j++) {
    result.push({ type: 'del', text: prevLines[j] })
  }

  // 4. Added lines (between prefix and suffix in new)
  for (let j = i; j <= c; j++) {
    result.push({ type: 'add', text: currLines[j] })
  }

  // 5. Common suffix
  for (let j = p + 1; j < prevLines.length; j++) {
    result.push({ type: 'same', text: prevLines[j] })
  }

  return result
}

// ─── Typewriter Code with Git Diff ──────────────────────────────────────────

const TYPING_MS = 32        // ms per character typed
const LINE_PAUSE_MS = 280   // pause between lines after fully typed

function CodeDisplay({ code, prevCode, codeHtml, onAnimationDone }) {
  const [diffEntries, setDiffEntries] = useState([])
  const [animState, setAnimState] = useState({
    diffIndex: -1,
    charProgress: 0,
    phase: 'idle',  // 'idle' | 'same' | 'typing' | 'deleting' | 'done'
  })
  const timerRef = useRef(null)
  const mountedRef = useRef(true)

  // Reset and start animation when code changes
  useEffect(() => {
    mountedRef.current = true
    const diff = computeLineDiff(prevCode, code)
    setDiffEntries(diff)
    setAnimState({ diffIndex: -1, charProgress: 0, phase: 'idle' })

    // Kick off animation after a small delay
    const t = setTimeout(() => {
      if (!mountedRef.current) return
      const idx = diff.findIndex(e => e.type !== 'same')
      if (idx === -1) {
        setAnimState({ diffIndex: diff.length - 1, charProgress: 0, phase: 'done' })
        onAnimationDone?.()
        return
      }
      // Show leading 'same' entries instantly
      setAnimState({ diffIndex: idx - 1, charProgress: 0, phase: 'same' })
      // Begin first animated entry
      const t2 = setTimeout(() => animateNext(diff, idx), 60)
      timerRef.current = t2
      return () => clearTimeout(t2)
    }, 80)
    timerRef.current = t
    return () => {
      mountedRef.current = false
      clearTimeout(timerRef.current)
    }
  }, [code, prevCode]) // eslint-disable-line react-hooks/exhaustive-deps

  const animateNext = useCallback((diff, idx) => {
    if (!mountedRef.current || idx >= diff.length) {
      setAnimState(prev => ({ ...prev, phase: 'done' }))
      onAnimationDone?.()
      return
    }
    const entry = diff[idx]
    if (entry.type === 'same') {
      setAnimState({ diffIndex: idx, charProgress: 0, phase: 'same' })
      timerRef.current = setTimeout(() => animateNext(diff, idx + 1), 40)
    } else if (entry.type === 'add') {
      setAnimState({ diffIndex: idx, charProgress: 0, phase: 'typing' })
      typeStep(diff, idx, 0)
    } else if (entry.type === 'del') {
      setAnimState({ diffIndex: idx, charProgress: 0, phase: 'deleting' })
      deleteStep(diff, idx, 0)
    }
  }, [onAnimationDone])

  const typeStep = useCallback((diff, idx, progress) => {
    if (!mountedRef.current) return
    const text = diff[idx].text
    if (progress >= text.length) {
      setAnimState({ diffIndex: idx, charProgress: text.length, phase: 'typing' })
      timerRef.current = setTimeout(() => animateNext(diff, idx + 1), LINE_PAUSE_MS)
      return
    }
    setAnimState({ diffIndex: idx, charProgress: progress + 1, phase: 'typing' })
    timerRef.current = setTimeout(() => typeStep(diff, idx, progress + 1), TYPING_MS)
  }, [animateNext])

  const deleteStep = useCallback((diff, idx, progress) => {
    if (!mountedRef.current) return
    const text = diff[idx].text
    if (progress >= text.length) {
      // Line fully erased — output empty text
      setAnimState({ diffIndex: idx, charProgress: text.length, phase: 'deleting' })
      timerRef.current = setTimeout(() => animateNext(diff, idx + 1), LINE_PAUSE_MS)
      return
    }
    setAnimState({ diffIndex: idx, charProgress: progress + 1, phase: 'deleting' })
    timerRef.current = setTimeout(() => deleteStep(diff, idx, progress + 1), TYPING_MS)
  }, [animateNext])

  return (
    <div className={styles.codeDisplay}>
      <div className={styles.codeHeader}>
        <span className={styles.codeLang}>Python</span>
        <div className={styles.codeDots}>
          <span style={{ background: '#ff5f56' }} />
          <span style={{ background: '#ffbd2e' }} />
          <span style={{ background: '#27c93f' }} />
        </div>
      </div>
      <pre className={styles.codeBlock}>
        <code>
          {diffEntries.length === 0 ? (
            <div className={styles.codeLine}>
              <span className={styles.lineNumber}>1</span>
              <span className={styles.lineGutter}>&nbsp;</span>
              <span className={styles.lineContent}><span className={styles.emptyLine}>&nbsp;</span></span>
            </div>
          ) : diffEntries.map((entry, idx) => {
            const isPast = idx < animState.diffIndex
            const isCurrent = idx === animState.diffIndex
            const isFuture = idx > animState.diffIndex && entry.type !== 'same'
            const isAnimating = isCurrent && (animState.phase === 'typing' || animState.phase === 'deleting')
            const isReady = isPast || (isCurrent && animState.phase === 'same') || (isPast && animState.phase === 'done')

            // Determine display text
            let displayText
            if (isReady || (isCurrent && animState.phase === 'same')) {
              displayText = entry.text
            } else if (isCurrent && animState.phase === 'typing') {
              displayText = entry.text.substring(0, animState.charProgress)
            } else if (isCurrent && animState.phase === 'deleting') {
              displayText = entry.text.substring(0, entry.text.length - animState.charProgress)
            } else if (isFuture && entry.type === 'add') {
              displayText = ''   // Future additions not shown yet
            } else if (isFuture && entry.type === 'del') {
              displayText = entry.text  // Show future deletions as still present
            } else {
              displayText = entry.text
            }

            // Determine CSS classes
            const lineCls = [
              styles.codeLine,
              entry.type === 'add' ? styles.lineTypeAdd : '',
              entry.type === 'del' ? styles.lineTypeDel : '',
              isAnimating ? styles.lineAnimating : '',
              isCurrent && animState.phase === 'typing' ? styles.lineAddTyping : '',
              isCurrent && animState.phase === 'deleting' ? styles.lineDelTyping : '',
              !isFuture && entry.type === 'del' ? styles.lineDeleted : '',
            ].filter(Boolean).join(' ')

            const gutter = entry.type === 'add' ? '+' : entry.type === 'del' ? '-' : ' '
            const gutterCls = [
              styles.lineGutter,
              entry.type === 'add' ? styles.gutterAdd : '',
              entry.type === 'del' ? styles.gutterDel : '',
            ].filter(Boolean).join(' ')

            const showCursor = isAnimating

            return (
              <div key={idx} className={lineCls}>
                <span className={styles.lineNumber}>{idx + 1}</span>
                <span className={gutterCls}>{gutter}</span>
                <span className={styles.lineContent}>
                  {isReady && codeHtml && codeHtml[idx]
                    ? <span dangerouslySetInnerHTML={{ __html: codeHtml[idx] || '&nbsp;' }} />
                    : <span>{displayText || <span className={styles.emptyLine}>&nbsp;</span>}</span>}
                  {showCursor && <span className={styles.typeCursor}>|</span>}
                </span>
              </div>
            )
          })}
        </code>
      </pre>
    </div>
  )
}

// ─── Explanation Panel ───────────────────────────────────────────────────────

function ExplanationPanel({ step, current, total }) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    setVisible(false)
    const t = setTimeout(() => setVisible(true), 150)
    return () => clearTimeout(t)
  }, [current])

  if (!step) return null

  return (
    <div className={`${styles.explanationPanel} ${visible ? styles.visible : ''}`}>
      <div className={styles.stepCounter}>
        <span className={styles.stepNum}>Step {current + 1}</span>
        <span className={styles.stepTotal}>/ {total}</span>
      </div>

      <div className={styles.stepTitles}>
        <h2 className={styles.stepTitle}>{step.title}</h2>
        <span className={styles.stepTitleEn}>{step.titleEn}</span>
      </div>

      <div className={styles.stepProgress}>
        <div className={styles.progressTrack}>
          <div
            className={styles.progressFill}
            style={{ width: `${((current + 1) / total) * 100}%` }}
          />
        </div>
        <span className={styles.progressPct}>{Math.round(((current + 1) / total) * 100)}%</span>
      </div>

      <div
        className={styles.explanationContent}
        dangerouslySetInnerHTML={{ __html: mdToHtml(step.explanation) }}
      />
    </div>
  )
}

// ─── Visualization Router ────────────────────────────────────────────────────

function AlgorithmVisualization({ step }) {
  if (!step || !step.visualizationData) return null
  const vd = step.visualizationData

  switch (step.visualizationType) {
    case 'intro':
      return (
        <div className={styles.vizIntro}>
          <div className={styles.vizIntroIcon}>⎇</div>
          <div className={styles.vizIntroText}>阅读题目，理解需求</div>
        </div>
      )
    case 'code-only':
      return (
        <div className={styles.vizHint}>
          <span className={styles.vizHintIcon}>✎</span>
          编写函数结构
        </div>
      )
    case 'map-create':
      return (
        <div className={styles.vizSplit}>
          <ArrayVisualizer state={vd.arrayState} currentIndex={vd.currentIndex} />
          <MapVisualizer mapContents={vd.mapContents} />
        </div>
      )
    case 'array-iteration':
      return (
        <div className={styles.vizSplit}>
          <ArrayVisualizer state={vd.arrayState} currentIndex={vd.currentIndex} />
          <MapVisualizer mapContents={vd.mapContents} />
          {vd.complement !== undefined && (
            <div className={styles.complementBadge}>
              complement = {vd.complement}
              {vd.found ? <span className={styles.foundTag}>✓ 命中!</span> : <span className={styles.missTag}>未找到</span>}
            </div>
          )}
        </div>
      )
    case 'map-add':
      return (
        <div className={styles.vizSplit}>
          <ArrayVisualizer state={vd.arrayState} currentIndex={vd.currentIndex} />
          <MapVisualizer mapContents={vd.mapContents} />
          <div className={styles.mapAction}>
            map.set({vd.mapKey}, {vd.mapValue}) → 存入 Map
          </div>
        </div>
      )
    case 'map-found':
      return (
        <div className={styles.vizSplit}>
          <ArrayVisualizer state={vd.arrayState} currentIndex={vd.currentIndex} highlightedIndices={[vd.foundIndex, vd.currentIndex]} />
          <MapVisualizer mapContents={vd.mapContents} />
          <div className={styles.mapActionSuccess}>
            map.has({vd.complement}) = true! → 找到索引 [{vd.foundIndex}, {vd.currentIndex}]
          </div>
        </div>
      )
    case 'result':
      return (
        <div className={styles.vizSplit}>
          <ArrayVisualizer state={vd.arrayState} highlightedIndices={vd.highlightedIndices} />
          <MapVisualizer mapContents={vd.mapContents} />
          <ResultVisualizer result={vd.result} highlightedIndices={vd.highlightedIndices} />
        </div>
      )
    default:
      return null
  }
}

// ─── Main Component ──────────────────────────────────────────────────────────

export default function AlgoVisualizerPage() {
  useDocumentTitle('Algorithm Lab - 算法可视化')
  const [currentStep, setCurrentStep] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playSpeed, setPlaySpeed] = useState(3500)
  const [direction, setDirection] = useState('forward')
  const [animDone, setAnimDone] = useState(false)
  const playRef = useRef(null)
  const [fadeKey, setFadeKey] = useState(0)
  const stepRef = useRef(currentStep)
  stepRef.current = currentStep

  const algorithms = algoIndex
  const currentAlgo = algoData
  const steps = currentAlgo?.steps || []
  const totalSteps = steps.length
  const hasPrev = currentStep > 0
  const hasNext = currentStep < totalSteps - 1

  // Reset animation state on step change
  const handleStepChange = useCallback((idx) => {
    setCurrentStep(idx)
    setAnimDone(false)
    setFadeKey(f => f + 1)
  }, [])

  // Called by CodeDisplay when typewriter animation finishes
  const handleAnimDone = useCallback(() => {
    setAnimDone(true)
  }, [])

  // Keyboard navigation
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault()
        if (hasNext) handleStepChange(currentStep + 1)
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault()
        if (hasPrev) handleStepChange(currentStep - 1)
      } else if (e.key === ' ') {
        e.preventDefault()
        setIsPlaying(p => !p)
        if (isPlaying) {
          setAnimDone(true)
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [currentStep, totalSteps, isPlaying, hasNext, hasPrev, handleStepChange])

  const goTo = useCallback((idx) => {
    if (idx < 0 || idx >= totalSteps) return
    handleStepChange(idx)
  }, [totalSteps, handleStepChange])

  const goNext = useCallback(() => {
    if (hasNext) handleStepChange(currentStep + 1)
  }, [hasNext, currentStep, handleStepChange])

  const goPrev = useCallback(() => {
    if (hasPrev) handleStepChange(currentStep - 1)
  }, [hasPrev, currentStep, handleStepChange])

  const togglePlay = useCallback(() => {
    setIsPlaying(p => {
      if (p) setAnimDone(true)
      return !p
    })
  }, [])

  // Auto-play — waits for animation to finish, then advances
  useEffect(() => {
    if (!isPlaying) {
      if (playRef.current) clearTimeout(playRef.current)
      return
    }
    // Wait for typewriter animation to finish
    if (!animDone) return

    const tick = () => {
      if (stepRef.current < totalSteps - 1) {
        handleStepChange(stepRef.current + 1)
      } else {
        setIsPlaying(false)
      }
    }
    playRef.current = setTimeout(tick, playSpeed)
    return () => { if (playRef.current) clearTimeout(playRef.current) }
  }, [isPlaying, animDone, totalSteps, playSpeed, handleStepChange])

  const step = steps[currentStep]

  return (
    <div className={styles.page}>
      {/* Top Navigation Bar */}
      <header className={styles.topBar}>
        <div className={styles.topLeft}>
          <h1 className={styles.topTitle}>Algorithm Lab</h1>
          <div className={styles.algoMeta}>
            <span className={styles.algoName}>{currentAlgo.title}</span>
            <span className={`${styles.diffBadge} ${styles[currentAlgo.difficulty]}`}>
              {currentAlgo.difficulty}
            </span>
            <span className={styles.testCase}>{currentAlgo.testCase}</span>
          </div>
        </div>
        <div className={styles.topRight}>
          <span className={styles.keyHint}>← →</span>
          <span className={styles.keyHintLabel}>切换步骤</span>
          <span className={styles.keyDivider}>|</span>
          <span className={styles.keyHint}>Space</span>
          <span className={styles.keyHintLabel}>自动播放</span>
        </div>
      </header>

      {/* Main Content */}
      <div className={styles.mainContent}>
        {/* Left Panel */}
        <div className={styles.leftPanel}>
          <div className={styles.codeSection} key={`code-${fadeKey}`}>
            <CodeDisplay
              code={step?.code || ''}
              prevCode={currentStep > 0 ? steps[currentStep - 1]?.code : ''}
              codeHtml={step?.codeHtml || []}
              onAnimationDone={handleAnimDone}
            />
          </div>
          <div className={styles.vizSection} key={`viz-${fadeKey}`}>
            <AlgorithmVisualization step={step} />
          </div>
        </div>

        {/* Right Panel */}
        <div className={styles.rightPanel} key={`right-${fadeKey}`}>
          <ExplanationPanel
            step={step}
            current={currentStep}
            total={totalSteps}
          />
        </div>
      </div>

      {/* Bottom Navigation */}
      <footer className={styles.bottomBar}>
        <div className={styles.navControls}>
          <button
            className={`${styles.navBtn} ${!hasPrev ? styles.disabled : ''}`}
            onClick={goPrev}
            disabled={!hasPrev}
            title="上一步 (←)"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            <span>上一步</span>
          </button>

          <button
            className={`${styles.playBtn} ${isPlaying ? styles.isPlaying : ''}`}
            onClick={togglePlay}
            title="自动播放 (Space)"
          >
            {isPlaying ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="4" width="4" height="16" rx="1" />
                <rect x="14" y="4" width="4" height="16" rx="1" />
              </svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="8,5 19,12 8,19" />
              </svg>
            )}
            <span>{isPlaying ? '暂停' : '播放'}</span>
          </button>

          <div className={styles.speedControl}>
            <span className={styles.speedLabel}>速度</span>
            <input
              type="range"
              min="500"
              max="4000"
              step="100"
              value={playSpeed}
              onChange={e => setPlaySpeed(Number(e.target.value))}
              className={styles.speedSlider}
            />
            <span className={styles.speedValue}>{(playSpeed / 1000).toFixed(1)}s</span>
          </div>

          <button
            className={`${styles.navBtn} ${!hasNext ? styles.disabled : ''}`}
            onClick={goNext}
            disabled={!hasNext}
            title="下一步 (→)"
          >
            <span>下一步</span>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        </div>

        <div className={styles.stepDots}>
          {steps.map((s, i) => (
            <button
              key={i}
              className={`${styles.stepDot} ${i === currentStep ? styles.active : ''} ${i < currentStep ? styles.done : ''}`}
              onClick={() => goTo(i)}
              title={`${s.title} (${s.titleEn})`}
            >
              <span className={styles.dotTooltip}>{s.title}</span>
            </button>
          ))}
        </div>
      </footer>
    </div>
  )
}
