import { useEffect, useMemo, useRef, useState } from 'react'
import { ACTS, GATES, SKILLS } from '../data/gates.js'
import { useReversingSession } from '../hooks/useReversingSession.js'
import { useHintProgress } from '../hooks/useHintProgress.js'
import { GateCard } from '../components/GateCard.jsx'
import { ShardBoard } from '../components/ShardBoard.jsx'
import * as api from '../services/reversingApi.js'
import styles from './ReversingPage.module.css'

export default function ReversingPage() {
  const { hb, state, error, ready } = useReversingSession()
  const { revealed, reveal, collapse } = useHintProgress()

  const [staleNote, setStaleNote] = useState('')
  const [attestNote, setAttestNote] = useState('')
  const [graduate, setGraduate] = useState(false)

  const attestFired = useRef(false)

  const shards = state?.shards ?? {}
  const doneCount = useMemo(
    () => GATES.filter((g) => shards[g.n]).length,
    [shards]
  )

  // 站点自己的握手——故意用一份过期的凭据链。它会失败，这是剧情。
  useEffect(() => {
    if (!ready) {
      return undefined
    }
    let alive = true

    ;(async () => {
      const ts = Math.floor(Date.now() / 1000)
      const client = 'hb-web/1.0'
      const nonce = api.randomNonce()
      const res = await api.handshake({ ts, client, nonce, sig: '0'.repeat(64) })
      if (!alive) {
        return
      }
      const msg = res.data?.msg ?? `HTTP ${res.status}`
      console.warn(
        '%c[hb] E_CREDENTIAL_STALE — 站点自己的握手被拒：' + msg,
        'color:#a65131;font-weight:700'
      )
      setStaleNote(`${msg}（trace ${res.data?.trace_id ?? '-'}）`)
    })()

    return () => {
      alive = false
    }
  }, [ready])

  // 碎片够算 K4 之后，页面自己去取一次声明——但只解前 16 位。
  useEffect(() => {
    if (!ready || !hb || attestFired.current) {
      return
    }
    if (![0, 1, 2, 3].every((n) => shards[n])) {
      return
    }
    attestFired.current = true

    ;(async () => {
      const k4 = hb.crypto.sha256([0, 1, 2, 3].map((n) => shards[n]).join(''))
      const ts = Math.floor(Date.now() / 1000)
      const client = 'hb-web/1.0'
      const nonce = api.randomNonce()
      const sig = hb.crypto.hmac(k4, `${ts}|${client}|${nonce}`)

      const res = await api.attest({ ts, client, nonce, sig })
      if (!res.ok) {
        setAttestNote(`attest 被拒：${res.data?.msg ?? res.status}`)
        return
      }

      const head = hb.gate5.decodeHead(k4, res.data.ct)
      hb.gate5.audit()
      setAttestNote(
        `响应 ${res.data.ct.length / 2} 字节，页面只用了前 ${head.length} 个字符：${head}`
      )
    })()
  }, [ready, hb, shards])

  if (error) {
    return (
      <main className={styles.page}>
        <section className="panel">
          <h1 className={styles.title}>内核加载失败</h1>
          <p className={styles.sectionNote}>{String(error.message ?? error)}</p>
        </section>
      </main>
    )
  }

  return (
    <main className={styles.page}>
      <header className={`hero-panel ${styles.hero}`}>
        <span className="hero-chip">F12 逆向挑战</span>
        <h1 className={styles.title}>源码里埋了一套题</h1>
        <p className={styles.lede}>
          这个页面看得见的部分只是一份说明。真正的题目在 <code>F12</code> 里——
          在 <code>public/reversing/js/</code> 那些没有被压缩的脚本中。九关全部打通之后，
          你会拿到一个 QQ 群号。
        </p>
        <div className={`toolbar ${styles.heroStats}`}>
          <div className={styles.stat}>
            <span className="metric-value">{doneCount}</span>
            <span className="metric-label">已通过</span>
          </div>
          <div className={styles.stat}>
            <span className="metric-value">9</span>
            <span className="metric-label">总关卡</span>
          </div>
          <div className={styles.stat}>
            <span className="metric-value">5</span>
            <span className="metric-label">纯本地</span>
          </div>
          <div className={styles.stat}>
            <span className="metric-value">4</span>
            <span className="metric-label">需联网</span>
          </div>
        </div>
        <p className={styles.fine}>
          进度只存在你自己的浏览器里。服务器不记录任何人——没有账号，没有排行榜，
          没有会话。它只做一件事：验证你手上的东西对不对。
        </p>
      </header>

      {state?.armed && (
        <div className={`panel ${styles.alarm}`}>
          <span>第 3 关的哨兵正在运行——每 137 毫秒一次断点。</span>
          <button type="button" className={styles.hintButton} onClick={() => hb.disarm()}>
            让它停下
          </button>
        </div>
      )}

      <section className={styles.section}>
        <header className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>需要用到的东西</h2>
        </header>
        <p className={styles.sectionNote}>
          这些是九关会考到的技能。知道要考什么，不等于知道怎么考——这一区就是提示的第 0 层。
        </p>
        <div className={styles.skills}>
          {SKILLS.map((s) => (
            <div key={s.key} className={`tip-card ${styles.skill}`}>
              <strong className={styles.skillLabel}>{s.label}</strong>
              <span className={styles.skillNote}>{s.note}</span>
            </div>
          ))}
        </div>
      </section>

      {ACTS.map((act) => (
        <section key={act.id} className={styles.section}>
          <header className={styles.sectionHead}>
            <h2 className={styles.sectionTitle}>{act.title}</h2>
            <span className="tag">{act.note}</span>
          </header>

          <div className={styles.gates}>
            {GATES.filter((g) => g.act === act.id).map((gate) => (
              <GateCard
                key={gate.n}
                gate={gate}
                done={!!shards[gate.n]}
                revealedCount={revealed[gate.n] ?? 0}
                onReveal={() => reveal(gate.n, gate.hints.length)}
                onCollapse={() => collapse(gate.n)}
              >
                {gate.n === 4 && staleNote && (
                  <p className={styles.gateExtra}>
                    <span className={styles.errTag}>E_CREDENTIAL_STALE</span>
                    {staleNote}
                  </p>
                )}
                {gate.n === 5 && attestNote && (
                  <p className={styles.gateExtra}>
                    <span className={styles.okTag}>attest</span>
                    {attestNote}
                  </p>
                )}
              </GateCard>
            ))}
          </div>
        </section>
      ))}

      <ShardBoard hb={hb} state={state} onGraduate={() => setGraduate(true)} />

      {graduate && (
        <div className={`panel ${styles.graduatedBanner}`}>
          <strong>通关。</strong>
          <span>九关全部打通。这套题没有存档，也没有记录——你拿走的只有那个群号。</span>
        </div>
      )}

      <footer className={styles.footer}>
        <span>
          build {state?.build ?? '--------'} · 逃生舱：在地址栏后面加 <code>?debug=1</code>
        </span>
      </footer>
    </main>
  )
}
