/**
 * 动态注入经典 <script>。
 *
 * 刻意不用 eval / new Function / import()：
 * 只有真实的 <script src> 才能让谜题文件在 DevTools 的 Sources 面板里
 * 以独立文件条目出现，从而可以被断点、被通读。这是游戏的前提。
 *
 * 这些文件在 public/reversing/js/ 下，Vite 原样拷贝，不经打包器。
 */

const pending = new Map()

export function loadScript(src) {
  if (pending.has(src)) {
    return pending.get(src)
  }

  const promise = new Promise((resolve, reject) => {
    const el = document.createElement('script')
    el.src = src
    el.async = false
    el.onload = () => resolve(src)
    el.onerror = () => reject(new Error(`脚本加载失败：${src}`))
    document.head.appendChild(el)
  })

  pending.set(src, promise)
  return promise
}
