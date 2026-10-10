import styles from './ResultView.module.css'
import { extractErrorMessage } from './EndpointForm.jsx'

export default function ResultView({ loading, error, result }) {
  if (loading) {
    return <div className={styles.note}>正在请求…</div>
  }

  if (error) {
    const hint =
      error instanceof TypeError && /fetch/i.test(error.message)
        ? '（fetch 失败：后端可能没启动。cd backend && PYTHONPATH=src uv run uvicorn rt_backend.main:app --port 8080）'
        : ''
    return <div className={styles.banner}>{`请求失败：${error.message}${hint}`}</div>
  }

  if (!result) return null

  if (!result.ok) {
    const msg = extractErrorMessage(result.data) || '(无响应体)'
    const trace = result.data?.trace_id ? ` · trace_id=${result.data.trace_id}` : ''
    return (
      <div className={styles.banner}>
        HTTP {result.status}：{msg}
        {trace}
      </div>
    )
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.statusLine}>HTTP {result.status} ✓</div>
      <details open className={styles.details}>
        <summary>响应 JSON</summary>
        <pre className={styles.pre}>{JSON.stringify(result.data, null, 2)}</pre>
      </details>
    </div>
  )
}
