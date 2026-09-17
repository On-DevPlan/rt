import { useEffect, useState } from 'react'
import { loadScript } from '../utils/loadScript.js'

/**
 * 谜题文件按依赖顺序注入。全部来自 public/reversing/js/，
 * 不经打包器，在 DevTools 里以独立文件出现。
 */
const SCRIPTS = [
  '/reversing/js/hb-crypto.js',
  '/reversing/js/hb-core.js',
  '/reversing/js/hb-gate-01.js',
  '/reversing/js/hb-gate-02.js',
  '/reversing/js/hb-gate-03.js',
  '/reversing/js/hb-gate-05.js',
  '/reversing/js/hb-gate-06.js'
]

// 模块级：StrictMode 会双跑 effect，但内核只该启动一次
let booted = false

export function useReversingSession() {
  const [hb, setHb] = useState(null)
  const [state, setState] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    let unsubscribe = null

    ;(async () => {
      try {
        for (const src of SCRIPTS) {
          await loadScript(src)
        }
        if (!alive) {
          return
        }

        const HB = window.HB
        if (!HB) {
          throw new Error('内核未挂载到 window.HB')
        }

        if (!booted) {
          HB._bootFn()
          booted = true
        }

        unsubscribe = HB.on(setState)
        setHb(HB)
        setState(HB.state())
      } catch (e) {
        if (alive) {
          setError(e)
        }
      }
    })()

    return () => {
      alive = false
      if (unsubscribe) {
        unsubscribe()
      }
    }
  }, [])

  return { hb, state, error, ready: state !== null }
}
