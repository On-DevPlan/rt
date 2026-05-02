import { useEffect, useMemo, useRef, useState } from 'react'

const HOVER_DELAY_MS = 3000

const story = {
  title: 'The Night Train',
  level: 'B1 Reading Practice',
  summary: 'A short English scene designed for sentence-by-sentence focus reading.',
  sentences: [
    'Maya arrived at the station just as the evening sky turned deep blue.',
    'She was tired from work, but the quiet platform gave her a strange feeling of freedom.',
    'A man in a brown coat played soft music near the ticket gate, and a few travelers slowed down to listen.',
    'When the train finally appeared, its windows shone like a moving line of warm light.',
    'Maya found her seat, placed her bag beside her, and watched the city fade behind the glass.',
    'Across the aisle, a child whispered questions about every station they passed.',
    'The mother answered each one with patience, as if the journey itself was a story worth telling.',
    'By the time the train entered the mountains, Maya had stopped thinking about tomorrow and started enjoying the ride.'
  ]
}

function SentenceCard({ sentence, index, isActive, isCompleted, progress, onEnter, onLeave }) {
  return (
    <button
      type="button"
      className={`sentence-card${isActive ? ' active' : ''}${isCompleted ? ' completed' : ''}`}
      onMouseEnter={() => onEnter(index)}
      onFocus={() => onEnter(index)}
      onMouseLeave={onLeave}
      onBlur={onLeave}
      style={{
        '--sentence-progress': `${Math.max(0, Math.min(progress, 1)) * 100}%`
      }}
    >
      <span className="sentence-index">{String(index + 1).padStart(2, '0')}</span>
      <span className="sentence-text">{sentence}</span>
    </button>
  )
}

export default function SentenceReaderPage() {
  const [activeIndex, setActiveIndex] = useState(null)
  const [progress, setProgress] = useState(0)
  const [completedIndex, setCompletedIndex] = useState(null)
  const [lastTriggeredIndex, setLastTriggeredIndex] = useState(null)
  const hoverStartRef = useRef(0)
  const rafRef = useRef(0)
  const timerRef = useRef(0)

  const activeSentence = activeIndex === null ? null : story.sentences[activeIndex]
  const remainingMs = useMemo(() => Math.max(0, Math.ceil((1 - progress) * HOVER_DELAY_MS)), [progress])

  useEffect(() => {
    if (activeIndex === null) {
      setProgress(0)
      return undefined
    }

    hoverStartRef.current = performance.now()
    setProgress(0)
    setCompletedIndex(null)

    const tick = (now) => {
      const nextProgress = Math.min((now - hoverStartRef.current) / HOVER_DELAY_MS, 1)
      setProgress(nextProgress)

      if (nextProgress < 1) {
        rafRef.current = window.requestAnimationFrame(tick)
      }
    }

    rafRef.current = window.requestAnimationFrame(tick)
    timerRef.current = window.setTimeout(() => {
      setCompletedIndex(activeIndex)
      setLastTriggeredIndex(activeIndex)
      setProgress(1)
      window.alert(`Read aloud: ${story.sentences[activeIndex]}`)
    }, HOVER_DELAY_MS)

    return () => {
      window.cancelAnimationFrame(rafRef.current)
      window.clearTimeout(timerRef.current)
    }
  }, [activeIndex])

  const handleEnter = (index) => {
    setActiveIndex(index)
  }

  const handleLeave = () => {
    setActiveIndex(null)
    setCompletedIndex(null)
    setProgress(0)
  }

  return (
    <div className="page-stack">
      <section className="reading-layout">
        <article className="reading-story-panel">
          <div className="reading-story-header">
            <div>
              <span className="reading-kicker">{story.level}</span>
              <h3>{story.title}</h3>
              <p>{story.summary}</p>
            </div>
            <div className="reading-legend">
              <span className="legend-pill">Hover to focus</span>
              <span className="legend-pill">3s to trigger</span>
            </div>
          </div>

          <div className="sentence-grid">
            {story.sentences.map((sentence, index) => (
              <SentenceCard
                key={index}
                index={index}
                sentence={sentence}
                isActive={activeIndex === index}
                isCompleted={completedIndex === index}
                progress={activeIndex === index ? progress : 0}
                onEnter={handleEnter}
                onLeave={handleLeave}
              />
            ))}
          </div>
        </article>

        <aside className="reading-aside">
          <div className="reading-status-card">
            <span className="reading-kicker">Focus State</span>
            <h3>{activeSentence ? `Sentence ${activeIndex + 1}` : 'Waiting for hover'}</h3>
            <p>
              {activeSentence
                ? activeSentence
                : 'Move the cursor onto any sentence card. The border will begin to draw around it.'}
            </p>
            <div className="focus-meter" aria-hidden="true">
              <div className="focus-meter-fill" style={{ width: `${progress * 100}%` }} />
            </div>
            <div className="reading-meta-row">
              <span>Delay</span>
              <strong>{activeSentence ? `${remainingMs} ms` : `${HOVER_DELAY_MS} ms`}</strong>
            </div>
            <div className="reading-meta-row">
              <span>Last trigger</span>
              <strong>{lastTriggeredIndex === null ? 'None' : `Sentence ${lastTriggeredIndex + 1}`}</strong>
            </div>
          </div>

          <div className="reading-status-card reading-notes-card">
            <span className="reading-kicker">Interaction Notes</span>
            <div className="list">
              <div className="list-row">
                <span>Enter another card</span>
                <code>reset timer</code>
              </div>
              <div className="list-row">
                <span>Leave current card</span>
                <code>cancel reading</code>
              </div>
              <div className="list-row">
                <span>Stay 3 seconds</span>
                <code>alert()</code>
              </div>
            </div>
          </div>
        </aside>
      </section>
    </div>
  )
}
