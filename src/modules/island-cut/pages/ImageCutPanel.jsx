import { useCallback, useEffect, useRef, useState } from 'react'
import { DEFAULT_PARAMS, cutImage, fullUrl, pieceUrl, zipUrl } from '../services/imageCutApi.js'
import styles from './IslandCutPage.module.css'

const MODE_OPTIONS = [
  { value: 'auto', label: '自动' },
  { value: 'alpha', label: '透明底' },
  { value: 'white', label: '白底' }
]

const PARAM_FIELDS = [
  { key: 'bg_threshold', label: '白底阈值', min: 200, max: 255, step: 1, hint: 'white 模式：≥ 该值的白色视为背景' },
  { key: 'alpha_threshold', label: 'Alpha 阈值', min: 0, max: 255, step: 1, hint: 'alpha 模式：> 该值视为前景；光晕粘连时调高' },
  { key: 'closing_iters', label: '闭运算', min: 0, max: 6, step: 1, hint: '填补主体断裂；相邻块粘连时设 0' },
  { key: 'min_area', label: '最小面积', min: 10, max: 20000, step: 10, hint: '低于此像素数的岛屿视为噪点丢弃' },
  { key: 'padding', label: '留白', min: 0, max: 100, step: 1, hint: '每块裁剪四周留白（像素）' },
  { key: 'small_min_area', label: '细节归属', min: 0, max: 500, step: 1, hint: '小连通域并入包含它的主岛，0 关闭' }
]

function fmtBytes(n) {
  if (n > 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${Math.max(1, Math.round(n / 1024))} KB`
}

export default function ImageCutPanel() {
  const [file, setFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [params, setParams] = useState(DEFAULT_PARAMS)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  // 切换/卸载时回收 objectURL
  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
  }, [previewUrl])

  const pickFile = useCallback((f) => {
    if (!f || !f.type.startsWith('image/')) return
    setFile(f)
    setPreviewUrl(URL.createObjectURL(f))
    setResult(null)
    setError('')
  }, [])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    pickFile(e.dataTransfer.files?.[0])
  }, [pickFile])

  const setParam = (key, value) => {
    setParams((p) => ({ ...p, [key]: value }))
  }

  const handleCut = async () => {
    if (!file || loading) return
    setLoading(true)
    setError('')
    try {
      setResult(await cutImage(file, params))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={`${styles.layout}`}>
      <section className="panel">
        <h3>1 · 上传源图</h3>
        <div
          className={`${styles.dropzone}${dragging ? ` ${styles.dropzoneActive}` : ''}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click() }}
        >
          {previewUrl ? (
            <img className={`${styles.preview} ${styles.checker}`} src={previewUrl} alt="源图预览" />
          ) : (
            <p className={styles.dropHint}>点击选择 或 拖入图片<br /><span>透明底 PNG / 白底 JPG 均可，≤ 50MB</span></p>
          )}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => pickFile(e.target.files?.[0])}
        />
        {file && (
          <p className={styles.fileMeta}>
            <span className="mono">{file.name}</span>
            <span>{fmtBytes(file.size)}</span>
          </p>
        )}

        <h3 className={styles.sectionTitle}>2 · 切割参数</h3>
        <div className={styles.modeRow}>
          {MODE_OPTIONS.map((m) => (
            <button
              key={m.value}
              type="button"
              className={`${styles.chip}${params.mode === m.value ? ` ${styles.chipActive}` : ''}`}
              onClick={() => setParam('mode', m.value)}
            >
              {m.label}
            </button>
          ))}
          <span className={styles.modeHint}>
            {params.mode === 'alpha' ? '前景 = alpha > 阈值'
              : params.mode === 'white' ? '边缘连通的白底为背景'
                : '按是否存在透明像素自动判定'}
          </span>
        </div>

        <div className={styles.paramList}>
          {PARAM_FIELDS.map((f) => (
            <label key={f.key} className={styles.paramRow} title={f.hint}>
              <span className={styles.paramLabel}>{f.label}</span>
              <input
                type="range"
                min={f.min}
                max={f.max}
                step={f.step}
                value={params[f.key]}
                onChange={(e) => setParam(f.key, Number(e.target.value))}
              />
              <input
                className={styles.paramValue}
                type="number"
                min={f.min}
                max={f.max}
                step={f.step}
                value={params[f.key]}
                onChange={(e) => setParam(f.key, Number(e.target.value))}
              />
            </label>
          ))}
          <div className={styles.paramRow}>
            <span className={styles.paramLabel}>连通域</span>
            <div className={styles.modeRow}>
              {[4, 8].map((c) => (
                <button
                  key={c}
                  type="button"
                  className={`${styles.chip}${params.connectivity === c ? ` ${styles.chipActive}` : ''}`}
                  onClick={() => setParam('connectivity', c)}
                >
                  {c} 邻域
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className={styles.actions}>
          <button type="button" className={styles.primaryBtn} disabled={!file || loading} onClick={handleCut}>
            {loading ? '切割中…' : '✂ 开始切割'}
          </button>
          <button type="button" className={styles.ghostBtn} onClick={() => setParams(DEFAULT_PARAMS)}>
            重置参数
          </button>
        </div>
        {error && <p className={styles.errorBox}>{error}</p>}
      </section>

      {result ? (
        <section className="panel">
          <div className="toolbar">
            <h3>切出 {result.piece_count} 块</h3>
            <span className="tag">{result.mode === 'alpha' ? '透明底模式' : '白底泛洪'}</span>
            <span className={styles.meta}>源图 {result.width}×{result.height} · {result.elapsed_ms}ms</span>
            <span className={styles.spring} />
            <a className={styles.primaryBtn} href={zipUrl(result.job_id)} download>
              ⬇ 下载 ZIP
            </a>
            <a className={styles.ghostBtn} href={fullUrl(result.job_id)} target="_blank" rel="noreferrer">
              整图透明底
            </a>
          </div>
          {result.piece_count === 0 ? (
            <div className="empty-card">
              <h3>没有切出岛屿</h3>
              <p>前景判定可能过严：白底图试试降低「白底阈值」，透明底图降低「Alpha 阈值」或「最小面积」。</p>
            </div>
          ) : (
            <div className={styles.pieceGrid}>
              {result.pieces.map((p) => (
                <figure key={p.id} className={styles.pieceCard}>
                  <a
                    className={`${styles.pieceThumb} ${styles.checker}`}
                    href={pieceUrl(result.job_id, p.filename)}
                    target="_blank"
                    rel="noreferrer"
                    title={`${p.filename} @ (${p.x}, ${p.y})`}
                  >
                    <img src={pieceUrl(result.job_id, p.filename)} alt={p.filename} loading="lazy" />
                  </a>
                  <figcaption>
                    <span className="mono">{p.filename}</span>
                    <span>{p.width}×{p.height} · {p.area.toLocaleString()}px</span>
                    <a
                      className={styles.pieceDownload}
                      href={pieceUrl(result.job_id, p.filename)}
                      download={p.filename}
                      title={`下载 ${p.filename}`}
                    >
                      ⬇
                    </a>
                  </figcaption>
                </figure>
              ))}
            </div>
          )}
        </section>
      ) : (
        <section className="empty-card">
          <h3>切割结果将显示在这里</h3>
          <p>
            算法：前景判定（alpha 阈值 / 白底泛洪）→ 形态学闭运算填补断裂 →
            连通域标记出岛屿 → 小细节并入主岛 → 按阅读顺序逐岛导出带透明通道的 PNG。
          </p>
          <p style={{ marginTop: 10 }}>
            上传图片并点击「开始切割」后，可逐块预览、单击放大，或一键打包下载全部切片。
          </p>
        </section>
      )}
    </div>
  )
}