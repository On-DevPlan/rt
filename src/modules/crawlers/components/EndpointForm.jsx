// 把表单原始输入按 spec.inputs 的类型归一化为后端期望的形状。
// 返回 { values, errors }：errors 非空时不应提交。

export function normalizeValues(inputs, raw) {
  const values = {}
  const errors = []

  for (const input of inputs) {
    const rawVal = raw?.[input.name]

    switch (input.type) {
      case 'number': {
        if (rawVal === '' || rawVal === undefined || rawVal === null) break // 留空 = 不传，用后端默认
        const n = Number(rawVal)
        if (Number.isNaN(n)) {
          errors.push(`「${input.label}」不是合法数字`)
          break
        }
        values[input.name] = n
        break
      }
      case 'bool':
        values[input.name] = Boolean(rawVal)
        break
      case 'list':
        values[input.name] = String(rawVal ?? '')
          .split('\n')
          .map((s) => s.trim())
          .filter(Boolean)
        break
      case 'json': {
        const s = String(rawVal ?? '').trim()
        if (!s) break
        try {
          values[input.name] = JSON.parse(s)
        } catch {
          errors.push(`「${input.label}」不是合法 JSON`)
        }
        break
      }
      case 'select':
        if (rawVal !== '' && rawVal !== undefined) values[input.name] = rawVal
        break
      default: // text
        if (rawVal !== '' && rawVal !== undefined && rawVal !== null) values[input.name] = rawVal
    }
  }

  return { values, errors }
}

// 后端两种错误信封：FastAPI HTTPException {detail} / 自定义 {code, msg}
export function extractErrorMessage(data) {
  if (!data) return ''
  if (typeof data.detail === 'string') return data.detail
  if (Array.isArray(data.detail)) {
    // FastAPI 422 validation errors: [{loc, msg, type}...]
    return data.detail.map((d) => `${(d.loc ?? []).join('.')}: ${d.msg}`).join('；')
  }
  if (data.msg) return data.msg
  if (data.error?.message) return data.error.message
  return JSON.stringify(data)
}

import styles from './EndpointForm.module.css'

export default function EndpointForm({ inputs, values, onChange, onSubmit, loading }) {
  return (
    <form
      className={styles.form}
      onSubmit={(e) => {
        e.preventDefault()
        if (!loading) onSubmit()
      }}
    >
      {inputs.map((input) => {
        const id = `ep-${input.name}`
        const rawVal = values[input.name]
        const type = input.type ?? 'text'

        if (type === 'bool') {
          return (
            <label key={input.name} className={styles.checkRow}>
              <input
                id={id}
                type="checkbox"
                checked={Boolean(rawVal)}
                onChange={(e) => onChange(input.name, e.target.checked)}
              />
              <span>{input.label}</span>
            </label>
          )
        }

        if (type === 'select') {
          return (
            <div key={input.name} className={styles.row}>
              <label htmlFor={id}>{input.label}</label>
              <select
                id={id}
                value={String(rawVal ?? '')}
                onChange={(e) => {
                  const opt = (input.options ?? []).find(
                    (o) => String(o.value) === e.target.value
                  )
                  onChange(input.name, opt ? opt.value : e.target.value)
                }}
              >
                {(input.options ?? []).map((o) => (
                  <option key={String(o.value)} value={String(o.value)}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
          )
        }

        if (type === 'list' || type === 'json') {
          return (
            <div key={input.name} className={styles.row}>
              <label htmlFor={id}>{input.label}</label>
              <textarea
                id={id}
                rows={type === 'json' ? 4 : 3}
                placeholder={input.placeholder}
                value={rawVal ?? ''}
                onChange={(e) => onChange(input.name, e.target.value)}
                spellCheck={false}
              />
            </div>
          )
        }

        // text / number（sensitive 走密码形态，避免旁人窥屏）
        return (
          <div key={input.name} className={styles.row}>
            <label htmlFor={id}>{input.label}</label>
            <input
              id={id}
              type={input.sensitive ? 'password' : type === 'number' ? 'number' : 'text'}
              step={type === 'number' ? 'any' : undefined}
              placeholder={input.placeholder}
              value={rawVal ?? ''}
              autoComplete={input.sensitive ? 'off' : undefined}
              onChange={(e) => onChange(input.name, e.target.value)}
              spellCheck={false}
            />
          </div>
        )
      })}

      <button type="submit" className={styles.submit} disabled={loading}>
        {loading ? '正在请求…' : '提交请求'}
      </button>
    </form>
  )
}
