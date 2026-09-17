import { useCallback, useState } from 'react'

const KEY = 'reversing.hints.v1'

function read() {
  try {
    const raw = window.localStorage.getItem(KEY)
    const parsed = raw ? JSON.parse(raw) : null
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function write(value) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(value))
  } catch {
    /* 隐私模式：退化成纯内存 */
  }
}

/**
 * 每关已展开的提示层数。
 *
 * 不设冷却、不做二次确认——这是帮忙，不是考试。
 * 进度只存在你自己的浏览器里，服务器不记录任何人。
 */
export function useHintProgress() {
  const [revealed, setRevealed] = useState(read)

  const reveal = useCallback((gateNumber, max) => {
    setRevealed((prev) => {
      const current = prev[gateNumber] ?? 0
      if (current >= max) {
        return prev
      }
      const next = { ...prev, [gateNumber]: current + 1 }
      write(next)
      return next
    })
  }, [])

  const collapse = useCallback((gateNumber) => {
    setRevealed((prev) => {
      const next = { ...prev, [gateNumber]: 0 }
      write(next)
      return next
    })
  }, [])

  return { revealed, reveal, collapse }
}
