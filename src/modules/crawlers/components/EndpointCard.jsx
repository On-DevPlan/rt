import { useState } from 'react'
import EndpointForm, { normalizeValues } from './EndpointForm.jsx'
import ResultView from './ResultView.jsx'
import styles from './EndpointCard.module.css'

// 数据驱动的端点卡片：spec = { id, title, description, method, path, inputs[], buildCurl, submit }
export default function EndpointCard({ spec }) {
  const [values, setValues] = useState(() => {
    const init = {}
    for (const input of spec.inputs) {
      init[input.name] = input.default ?? (input.type === 'bool' ? false : '')
    }
    return init
  })
  const [normErrors, setNormErrors] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  const onChange = (name, value) => {
    setValues((v) => ({ ...v, [name]: value }))
    setNormErrors([]) // 输入变化即清除上次的归一化错误
  }

  // curl 实时预览：用当前输入的归一化结果拼（JSON 非法时对应字段缺省，不抛错）
  const { values: norm } = normalizeValues(spec.inputs, values)
  let curl = ''
  try {
    curl = spec.buildCurl(norm)
  } catch {
    curl = spec.buildCurl({})
  }

  const handleSubmit = async () => {
    const { values: payload, errors } = normalizeValues(spec.inputs, values)
    if (errors.length > 0) {
      setNormErrors(errors)
      return
    }
    setNormErrors([])
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await spec.submit(payload)
      setResult(res)
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className={`panel ${styles.card}`}>
      <header className={styles.head}>
        <h3 className={styles.title}>{spec.title}</h3>
        <span className={`${styles.method} ${styles[spec.method.toLowerCase()]}`}>
          {spec.method}
        </span>
        <code className={styles.path}>{spec.path}</code>
      </header>

      <p className={styles.desc}>{spec.description}</p>

      {normErrors.length > 0 && (
        <div className={styles.inlineErrors}>
          {normErrors.map((e) => (
            <div key={e}>⚠️ {e}</div>
          ))}
        </div>
      )}

      <EndpointForm
        inputs={spec.inputs}
        values={values}
        onChange={onChange}
        onSubmit={handleSubmit}
        loading={loading}
      />

      <details className={styles.curlBox}>
        <summary>curl</summary>
        <pre>{curl}</pre>
      </details>

      <ResultView loading={loading} error={error} result={result} />
    </section>
  )
}
