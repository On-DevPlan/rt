import { useMemo, useState } from 'react'
import { copyText } from '../utils/clipboard.js'
import styles from '../pages/ReversingPage.module.css'

const ORDER = [0, 1, 2, 3, 4, 5, 6, 7]
const SERVER_GATES = new Set([4, 5, 7])

export function ShardBoard({ hb, state, onGraduate }) {
  const [drafts, setDrafts] = useState({})
  const [blob, setBlob] = useState('')
  const [answer, setAnswer] = useState(null)
  const [note, setNote] = useState('')

  const shards = state?.shards ?? {}
  const collected = ORDER.filter((n) => shards[n]).length
  const complete = collected === ORDER.length

  // K = sha256(S0 + S1 + ... + S7)
  const key = useMemo(() => {
    if (!complete || !hb) {
      return null
    }
    return hb.crypto.sha256(ORDER.map((n) => shards[n]).join(''))
  }, [complete, hb, shards])

  function record(n) {
    const value = (drafts[n] ?? '').trim().toLowerCase()
    if (!hb || !value) {
      return
    }
    if (!hb.setServerShard(n, value)) {
      setNote(`S${n} 得是 16 位小写 hex。`)
      return
    }
    setNote(`S${n} 已记入。`)
  }

  async function copy(value, label) {
    const ok = await copyText(value)
    setNote(ok ? `${label} 已复制。` : '复制失败，手动选中吧。')
  }

  function decryptFinale() {
    const raw = blob.trim().toLowerCase()
    if (!key) {
      setNote('碎片还没集齐。')
      return
    }
    if (!/^[0-9a-f]+$/.test(raw) || raw.length % 2 !== 0) {
      setNote('密文应该是偶数长度的 hex。')
      return
    }
    try {
      const plain = hb.crypto.decrypt(key, raw)
      setAnswer(plain)
      setNote('')
      onGraduate?.(plain)
    } catch {
      setNote('解不开。要么密文不对，要么碎片不对。')
    }
  }

  return (
    <section className={`panel ${styles.board}`}>
      <header className={styles.sectionHead}>
        <h2 className={styles.sectionTitle}>碎片</h2>
        <span className={`metric-value ${styles.boardCount}`}>
          {collected}
          <small>/8</small>
        </span>
      </header>

      <p className={styles.sectionNote}>
        前 5 片在浏览器里拿，后 3 片得跟服务器换。全部集齐才能拼出终章密钥。
        {state?.debug && ' 当前是 ?debug=1 模式，碎片已全部补齐。'}
      </p>

      <div className={styles.slots}>
        {ORDER.map((n) => {
          const value = shards[n]
          return (
            <div
              key={n}
              className={`${styles.slot}${value ? ` ${styles.slotFilled}` : ''}`}
            >
              <span className={styles.slotLabel}>S{n}</span>
              {value ? (
                <button
                  type="button"
                  className={styles.slotValue}
                  title="点击复制"
                  onClick={() => copy(value, `S${n}`)}
                >
                  {value}
                </button>
              ) : (
                <span className={styles.slotEmpty}>—</span>
              )}
            </div>
          )
        })}
      </div>

      {ORDER.some((n) => SERVER_GATES.has(n) && !shards[n]) && (
        <div className={styles.claimRow}>
          {ORDER.filter((n) => SERVER_GATES.has(n) && !shards[n]).map((n) => (
            <div key={n} className={styles.claimItem}>
              <label className={styles.claimLabel} htmlFor={`claim-${n}`}>
                从服务器换到的 S{n}
              </label>
              <div className="toolbar">
                <input
                  id={`claim-${n}`}
                  className={`search-input ${styles.claimInput}`}
                  value={drafts[n] ?? ''}
                  placeholder="16 位 hex"
                  onChange={(e) => setDrafts((p) => ({ ...p, [n]: e.target.value }))}
                  onKeyDown={(e) => e.key === 'Enter' && record(n)}
                />
                <button type="button" className={styles.hintButton} onClick={() => record(n)}>
                  记入
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {key && (
        <div className={`code-panel ${styles.keyPanel}`}>
          <span className={styles.keyLabel}>K = sha256(S0…S7)</span>
          <code className={styles.keyValue}>{key}</code>
          <button type="button" className={styles.ghostButton} onClick={() => copy(key, 'K')}>
            复制
          </button>
        </div>
      )}

      <div className={styles.finale}>
        <h3 className={styles.finaleTitle}>终章</h3>
        <p className={styles.sectionNote}>
          过了第 8 关之后，你会拿到一段密文。粘进来——页面用你集齐的 K 替你解开。
          密文来自服务器，K 只在你手上，两边缺一不可。
        </p>
        <div className="toolbar">
          <input
            className={`search-input ${styles.blobInput}`}
            value={blob}
            placeholder="final.blob（hex）"
            onChange={(e) => setBlob(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && decryptFinale()}
          />
          <button type="button" className={styles.hintButton} onClick={decryptFinale}>
            解开
          </button>
        </div>

        {answer && (
          <div className={styles.graduated}>
            <span className={styles.graduatedLabel}>解密结果</span>
            <strong className={styles.answer}>{answer}</strong>
            <p className={styles.sectionNote}>
              这就是群号。搜 QQ 群，或者直接把这段数字粘进 QQ 添加群。
            </p>
          </div>
        )}

        {note && <p className={styles.note}>{note}</p>}
      </div>
    </section>
  )
}
