import { useEffect, useRef, useState } from 'react'
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

function ProgressBar({ progress, hidden }) {
  if (hidden) return null
  const pct = Math.round(progress * 100)
  return (
    <div style={{ width: '100%', height: '10px', background: 'rgba(120, 80, 50, 0.15)', borderRadius: '999px', marginTop: '8px', overflow: 'hidden' }}>
      <div style={{ width: `${pct}%`, height: '100%', background: 'linear-gradient(90deg, #5c3d2e, #8b6343)', borderRadius: '999px', transition: 'width 0.05s linear', boxShadow: '0 0 8px rgba(92, 61, 46, 0.5)' }} />
    </div>
  )
}

function SentenceRow({ item, index, isActive, isRevealed, progress, onEnter, onLeave, cleanMode }) {
  return (
    <div className={`${styles.line}${isActive ? ` ${styles.lineActive}` : ''}`}>
      <button
        type="button"
        className={styles.sentenceButton}
        onMouseEnter={() => onEnter(index)}
        onFocus={() => onEnter(index)}
        onMouseLeave={onLeave}
        onBlur={onLeave}
      >
        <span className={styles.sentenceStack}>
          <span className={styles.sentenceEn}>{item.en}</span>
          {!cleanMode && <ProgressBar progress={isActive ? progress : 0} />}
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
  const intervalRef = useRef(0)
  const timerRef = useRef(0)

  useEffect(() => {
    if (activeIndex === null) {
      setProgress(0)
      return undefined
    }

    setProgress(0)

    const step = 50
    let elapsed = 0

    intervalRef.current = window.setInterval(() => {
      elapsed += step
      const newProgress = Math.min(elapsed / HOVER_DELAY_MS, 1)
      setProgress(newProgress)

      if (newProgress >= 1) {
        window.clearInterval(intervalRef.current)
      }
    }, step)

    timerRef.current = window.setTimeout(() => {
      setProgress(1)
      setRevealedIndexes((current) =>
        current.includes(activeIndex) ? current : [...current, activeIndex]
      )
    }, HOVER_DELAY_MS)

    return () => {
      window.clearInterval(intervalRef.current)
      window.clearTimeout(timerRef.current)
    }
  }, [activeIndex])

  const handleEnter = (index) => setActiveIndex(index)
  const handleLeave = () => setActiveIndex(null)

  const handleContextMenu = (e) => {
    e.preventDefault()
    setCleanMode((prev) => !prev)
  }

  return (
    <div className="page-stack">
      <section
        className={`${styles.shell}${cleanMode ? ` ${styles.cleanMode}` : ''}`}
        onContextMenu={handleContextMenu}
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
            />
          ))}
        </div>
      </section>
    </div>
  )
}
