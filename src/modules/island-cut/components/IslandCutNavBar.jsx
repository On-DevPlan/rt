import styles from './IslandCutNavBar.module.css'

export function IslandCutNavBar({ tabs, activeId, onChange }) {
  return (
    <nav className={styles.bar} role="tablist">
      {tabs.map((t) => {
        const active = t.id === activeId
        return (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={active}
            disabled={!!t.locked}
            title={t.locked ? t.lockReason : undefined}
            className={`${styles.tab}${active ? ` ${styles.tabActive}` : ''}${t.locked ? ` ${styles.tabLocked}` : ''}`}
            onClick={() => !t.locked && onChange(t.id)}
          >
            {t.label}
            {t.badge && <span className={styles.badge}>{t.badge}</span>}
            {t.locked && <span className={styles.badge} title={t.lockReason}>🔒</span>}
          </button>
        )
      })}
    </nav>
  )
}