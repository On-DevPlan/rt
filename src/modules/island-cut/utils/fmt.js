/** 通用：把字节数格式化为 "X.X MB" / "XXX KB"。 */
export function fmtSize(bytes) {
  if (bytes == null) return '—'
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`
  return `${bytes} B`
}