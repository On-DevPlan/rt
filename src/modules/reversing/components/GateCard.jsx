import { HintStack } from './HintStack.jsx'
import styles from '../pages/ReversingPage.module.css'

export function GateCard({ gate, done, revealedCount, onReveal, onCollapse, children }) {
  return (
    <article className={`panel ${styles.gateCard}${done ? ` ${styles.gateDone}` : ''}`}>
      <header className={styles.gateHead}>
        <span className={`metric-value ${styles.gateNo}`}>
          {String(gate.n).padStart(2, '0')}
        </span>

        <div className={styles.gateTitle}>
          <h3 className={styles.gateName}>
            {gate.name}
            {gate.hard && <span className={`tag ${styles.hardTag}`}>硬对抗</span>}
          </h3>
          <p className={styles.gateBrief}>{gate.brief}</p>
        </div>

        <span className={`tag ${done ? styles.statusDone : styles.statusPending}`}>
          {done ? '已通过' : '未通过'}
        </span>
      </header>

      {children}

      <HintStack
        gate={gate}
        revealedCount={revealedCount}
        onReveal={onReveal}
        onCollapse={onCollapse}
      />
    </article>
  )
}
