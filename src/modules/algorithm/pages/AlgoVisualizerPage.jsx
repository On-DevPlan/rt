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

// ─── Code Display with Line Diff ─────────────────────────────────────────────

function CodeDisplay({ code, prevCode }) {
  const codeRef = useRef(null)
  const [visibleLines, setVisibleLines] = useState(new Set())

  const currentLines = useMemo(() => code.split('\n'), [code])
  const prevLines = useMemo(() => (prevCode || '').split('\n'), [prevCode])

  useEffect(() => {
    if (!codeRef.current) return
    // Animate lines appearing
    const newLines = new Set()
    currentLines.forEach((line, i) => {
      const isNew = i >= prevLines.length || currentLines[i] !== (prevLines[i] || '')
      if (isNew) newLines.add(i)
    })
    setVisibleLines(newLines)
  }, [code, prevLines, currentLines])

  return (
    <div className={styles.codeDisplay} ref={codeRef}>
      <div className={styles.codeHeader}>
        <span className={styles.codeLang}>JavaScript</span>
        <div className={styles.codeDots}>
          <span style={{ background: '#ff5f56' }} />
          <span style={{ background: '#ffbd2e' }} />
          <span style={{ background: '#27c93f' }} />
        </div>
      </div>
      <pre className={styles.codeBlock}>
        <code>
          {currentLines.map((line, i) => (
            <div
              key={i}
              className={`${styles.codeLine} ${visibleLines.has(i) ? styles.codeLineNew : ''}`}
              style={{ '--line-delay': `${i * 0.04}s` }}
            >
              <span className={styles.lineNumber}>{i + 1}</span>
              <span className={styles.lineContent}>
                {line || <span className={styles.emptyLine}>&nbsp;</span>}
              </span>
            </div>
          ))}
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
  const [playSpeed, setPlaySpeed] = useState(2000)
  const [direction, setDirection] = useState('forward')
  const playRef = useRef(null)
  const [fadeKey, setFadeKey] = useState(0)

  const algorithms = algoIndex
  const currentAlgo = algoData
  const steps = currentAlgo?.steps || []
  const totalSteps = steps.length
  const hasPrev = currentStep > 0
  const hasNext = currentStep < totalSteps - 1

  // Keyboard navigation
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault()
        goNext()
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault()
        goPrev()
      } else if (e.key === ' ') {
        e.preventDefault()
        togglePlay()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [currentStep, totalSteps, isPlaying])

  const goTo = useCallback((idx) => {
    if (idx < 0 || idx >= totalSteps) return
    setCurrentStep(idx)
    setFadeKey(f => f + 1)
  }, [totalSteps])

  const goNext = useCallback(() => {
    if (hasNext) goTo(currentStep + 1)
  }, [hasNext, currentStep, goTo])

  const goPrev = useCallback(() => {
    if (hasPrev) goTo(currentStep - 1)
  }, [hasPrev, currentStep, goTo])

  const togglePlay = useCallback(() => {
    setIsPlaying(p => !p)
  }, [])

  // Auto-play
  useEffect(() => {
    if (!isPlaying) {
      if (playRef.current) clearTimeout(playRef.current)
      return
    }

    const tick = () => {
      if (direction === 'forward') {
        if (hasNext) {
          goTo(currentStep + 1)
        } else {
          if (playRef.current) clearTimeout(playRef.current)
          setIsPlaying(false)
          return
        }
      } else {
        if (hasPrev) {
          goTo(currentStep - 1)
        } else {
          if (playRef.current) clearTimeout(playRef.current)
          setIsPlaying(false)
          return
        }
      }
    }

    playRef.current = setTimeout(tick, playSpeed)
    return () => { if (playRef.current) clearTimeout(playRef.current) }
  }, [isPlaying, currentStep, hasNext, hasPrev, direction, playSpeed, goTo])

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
