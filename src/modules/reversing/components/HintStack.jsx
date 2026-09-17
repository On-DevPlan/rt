import styles from '../pages/ReversingPage.module.css'

const TIER_LABEL = ['谜语', '方向', '步骤', '近答案']

/**
 * 渐进提示。点一次多一层，已展开的常驻。
 */
export function HintStack({ gate, revealedCount, onReveal, onCollapse }) {
  const total = gate.hints.length
  const shown = Math.min(revealedCount ?? 0, total)
  const exhausted = shown >= total

  return (
    <div className={styles.hints}>
      {shown > 0 && (
        <ol className={styles.hintList}>
          {gate.hints.slice(0, shown).map((text, index) => (
            <li key={index} className={`tip-card ${styles.hint}`}>
              <span className={styles.hintTier}>
                {TIER_LABEL[index] ?? `第 ${index + 1} 层`}
              </span>
              <p className={styles.hintText}>{text}</p>
            </li>
          ))}
        </ol>
      )}

      <div className="toolbar">
        <button
          type="button"
          className={styles.hintButton}
          onClick={onReveal}
          disabled={exhausted}
        >
          {shown === 0
            ? '获取提示'
            : exhausted
              ? '提示已全部展开'
              : `再给一层（${shown}/${total}）`}
        </button>

        {shown > 0 && (
          <button type="button" className={styles.ghostButton} onClick={onCollapse}>
            收起
          </button>
        )}
      </div>
    </div>
  )
}
