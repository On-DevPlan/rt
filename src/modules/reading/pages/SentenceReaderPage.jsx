import { useState, useRef, useCallback } from 'react'
import { useTTS } from '../hooks/useTTS'
import { tokenizeText } from '../utils/wordHighlighter'
import styles from './SentenceReaderPage.module.css'

const HOVER_DELAY_MS = 3000

const story = {
  title: 'The Night Train',
  level: 'B1 Reading Practice',
  summary: 'Hover on a sentence and stay still for three seconds to reveal its translation and learning focus.',
  sentences: [
    {
      en: 'Maya arrived at the station just as the evening sky turned deep blue.',
      zh: '傍晚的天空刚刚变成深蓝色时，玛雅到达了车站。',
      focus: ['just as = 正当', 'turned deep blue = 逐渐变成深蓝']
    },
    {
      en: 'She was tired from work, but the quiet platform gave her a strange feeling of freedom.',
      zh: '她下班后很疲惫，但安静的站台却给了她一种奇异的自由感。',
      focus: ['tired from work = 因工作而疲惫', 'gave her a feeling of = 让她产生……感觉']
    },
    {
      en: 'A man in a brown coat played soft music near the ticket gate, and a few travelers slowed down to listen.',
      zh: '一位穿棕色外套的男人在检票口附近演奏轻柔的音乐，几位旅客也放慢脚步听了下来。',
      focus: ['slowed down to listen = 放慢脚步去听', 'a few travelers = 几位旅客']
    },
    {
      en: 'When the train finally appeared, its windows shone like a moving line of warm light.',
      zh: '火车终于出现时，车窗像一条流动的暖光线一样闪亮。',
      focus: ['appeared = 出现', 'a moving line of warm light = 一条流动的暖光']
    },
    {
      en: 'Maya found her seat, placed her bag beside her, and watched the city fade behind the glass.',
      zh: '玛雅找到座位，把包放在身边，看着城市在窗外渐渐远去。',
      focus: ['placed her bag beside her = 把包放在身边', 'fade behind the glass = 在窗外渐渐淡去']
    },
    {
      en: 'Across the aisle, a child whispered questions about every station they passed.',
      zh: '过道对面，一个孩子轻声问着他们经过的每一站。',
      focus: ['across the aisle = 在过道对面', 'whispered questions = 轻声提问']
    },
    {
      en: 'The mother answered each one with patience, as if the journey itself was a story worth telling.',
      zh: '母亲耐心地回答每一个问题，仿佛这段旅程本身就是一个值得讲述的故事。',
      focus: ['with patience = 耐心地', 'worth telling = 值得讲述']
    },
    {
      en: 'By the time the train entered the mountains, Maya had stopped thinking about tomorrow and started enjoying the ride.',
      zh: '等火车驶入山间时，玛雅已经不再想着明天，而开始享受这段旅程。',
      focus: ['By the time ... = 等到……的时候', 'started enjoying the ride = 开始享受这段行程']
    }
  ]
}

function ProgressDot({ progress, hidden, isRevealed }) {
  if (hidden) return null
  const radius = 5
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - progress)
  const fillOpacity = 0.3 + progress * 0.7

  return (
    <span style={{
      display: 'inline-block',
      width: '10px',
      height: '10px',
      borderRadius: '50%',
      marginLeft: '8px',
      verticalAlign: 'middle',
      position: 'relative',
    }}>
      <svg width="10" height="10" viewBox="0 0 10 10" style={{ position: 'absolute', top: 0, left: 0 }}>
        <circle cx="5" cy="5" r={radius} fill="rgba(120, 80, 50, 0.15)" />
        <circle
          cx="5"
          cy="5"
          r={radius}
          fill="#5c3d2e"
          fillOpacity={fillOpacity}
          stroke="#5c3d2e"
          strokeWidth="1.5"
          strokeOpacity={isRevealed ? 0 : 1}
          strokeDasharray={circumference}
          strokeDashoffset={isRevealed ? 0 : offset}
          transform="rotate(-90 5 5)"
          style={{ transition: 'stroke-dashoffset 0.05s linear, stroke-opacity 0.2s ease' }}
        />
        {isRevealed && (
          <circle cx="5" cy="5" r={radius - 2} fill="#5c3d2e" fillOpacity="0.6" />
        )}
      </svg>
    </span>
  )
}

function HighlightedSentence({ text, currentWordIndex, isPlaying }) {
  const tokens = tokenizeText(text)

  return (
    <span className={styles.sentenceEn}>
      {tokens.map((token, i) => {
        const isHighlighted = isPlaying && currentWordIndex >= 0 && i === currentWordIndex
        const prevWasHighlighted = isPlaying && currentWordIndex > 0 && i === currentWordIndex - 1
        const nextIsHighlighted = isPlaying && i === currentWordIndex + 1

        return (
          <span
            key={i}
            className={`
              ${styles.word}
              ${isHighlighted ? styles.wordHighlighted : ''}
              ${prevWasHighlighted ? styles.wordPassed : ''}
              ${nextIsHighlighted && !isHighlighted ? styles.wordUpcoming : ''}
            `}
          >
            {token.word}{i < tokens.length - 1 ? ' ' : ''}
          </span>
        )
      })}
    </span>
  )
}

function SentenceRow({ item, index, isActive, isRevealed, progress, onEnter, onLeave, cleanMode, isPlaying, currentWordIndex, onPlay }) {
  return (
    <div className={`${styles.line}${isActive ? ` ${styles.lineActive}` : ''}`}>
      <button
        type="button"
        className={styles.sentenceButton}
        onMouseEnter={() => onEnter(index)}
        onFocus={() => onEnter(index)}
        onMouseLeave={onLeave}
        onBlur={onLeave}
        onClick={() => onPlay(item.en)}
      >
        <span className={styles.sentenceStack}>
          {isPlaying && currentWordIndex >= 0 ? (
            <HighlightedSentence
              text={item.en}
              currentWordIndex={currentWordIndex}
              isPlaying={isPlaying}
            />
          ) : (
            <span className={styles.sentenceEn}>{item.en}</span>
          )}
          {!cleanMode && <ProgressDot progress={isActive ? progress : 0} isRevealed={isRevealed} />}
        </span>
      </button>

      {!cleanMode && (
        <div className={`${styles.detail}${isRevealed ? ` ${styles.detailVisible}` : ''}`}>
          <p className={styles.sentenceZh}>{item.zh}</p>
          <div className={styles.focusTags}>
            {item.focus.map((point) => (
              <span key={point} className={styles.focusTag}>{point}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function SentenceReaderPage() {
  const [activeIndex, setActiveIndex] = useState(null)
  const [progress, setProgress] = useState(0)
  const [revealedIndexes, setRevealedIndexes] = useState([])
  const [cleanMode, setCleanMode] = useState(false)

  const { isPlaying, currentWordIndex, error, play, stop } = useTTS({
    voice: 'en-US-AndrewNeural',
    rate: '-10%',
  })

  const intervalRef = useRef(0)
  const timerRef = useRef(0)

  const handleEnter = (index) => setActiveIndex(index)
  const handleLeave = () => setActiveIndex(null)

  const handlePlay = useCallback((text) => {
    if (isPlaying) {
      stop()
    } else {
      play(text)
    }
  }, [isPlaying, play, stop])

  return (
    <div className="page-stack">
      <section
        className={`${styles.shell}${cleanMode ? ` ${styles.cleanMode}` : ''}`}
        onContextMenu={(e) => {
          e.preventDefault()
          setCleanMode((prev) => !prev)
        }}
      >
        <header className={styles.header}>
          <div>
            <span className={styles.kicker}>{story.level}</span>
            <h2>{story.title}</h2>
            <p>{story.summary}</p>
          </div>
          <div className={styles.meta}>
            <div className={styles.chip}>
              <strong>{story.sentences.length}</strong>
              <span>sentences</span>
            </div>
            <div className={styles.chip}>
              <strong>{revealedIndexes.length}</strong>
              <span>revealed</span>
            </div>
            {isPlaying && (
              <button className={styles.stopButton} onClick={stop}>
                Stop
              </button>
            )}
            {error && <span style={{ color: '#c44', fontSize: '0.85rem' }}>{error}</span>}
          </div>
        </header>

        <div className={styles.copy}>
          {story.sentences.map((item, index) => (
            <SentenceRow
              key={index}
              item={item}
              index={index}
              isActive={activeIndex === index}
              isRevealed={revealedIndexes.includes(index)}
              progress={activeIndex === index ? progress : 0}
              onEnter={handleEnter}
              onLeave={handleLeave}
              cleanMode={cleanMode}
              isPlaying={isPlaying && revealedIndexes.includes(index)}
              currentWordIndex={currentWordIndex}
              onPlay={handlePlay}
            />
          ))}
        </div>
      </section>
    </div>
  )
}
