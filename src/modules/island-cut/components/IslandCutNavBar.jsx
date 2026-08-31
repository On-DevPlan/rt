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
            className={`${styles.tab}${active ? ` ${styles.tabActive}` : ''}`}
            onClick={() => onChange(t.id)}
          >
            {t.label}
            {t.badge && <span className={styles.badge}>{t.badge}</span>}
          </button>
        )
      })}
    </nav>
  )
}