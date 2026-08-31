import { useCallback, useEffect, useRef, useState } from 'react'
import {
  DEFAULT_PARAMS, cutVideo,
  sheetUrl, framesZipUrl, framesJsonUrl,
  previewApngUrl, previewWebpUrl,
} from '../services/videoSheetApi.js'
import styles from './IslandCutPage.module.css'

const PARAM_FIELDS = [
  { key: 'fps',              label: '帧率',   min: 1,   max: 30,  step: 1,  hint: '输出帧率（ffmpeg mpdecimate 去重帧后）' },
  { key: 'tol',              label: '色距容差', min: 1,   max: 255, step: 1,  hint: '> 水印最大色距才能吃掉水印' },
  { key: 'min_area',         label: '最小岛屿', min: 50, max: 5000, step: 50, hint: '低于此像素数的岛屿视为噪点丢弃' },
  { key: 'max_duration_sec', label: '时长上限', min: 10, max: 300, step: 10, hint: '超过抛 413' },
  { key: 'max_frames',       label: '帧数上限', min: 60, max: 1500, step: 30, hint: '超过抛 413' },
]

function fmtBytes(n) {
  if (n > 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${Math.max(1, Math.round(n / 1024))} KB`
}

export default function VideoSheetPanel() {
  const [file, setFile] = useState(null)
  const [videoUrl, setVideoUrl] = useState('')
  const [params, setParams] = useState(DEFAULT_PARAMS)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => () => {
    if (videoUrl) URL.revokeObjectURL(videoUrl)
  }, [videoUrl])

  const pickFile = useCallback((f) => {
    if (!f || !f.type.startsWith('video/')) return
    setFile(f)
    setVideoUrl(URL.createObjectURL(f))
    setResult(null)
    setError('')
  }, [])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    pickFile(e.dataTransfer.files?.[0])
  }, [pickFile])

  const setParam = (key, value) => setParams((p) => ({ ...p, [key]: value }))

  const handleCut = async () => {
    if (!file || loading) return
    setLoading(true)
    setError('')
    try {
      setResult(await cutVideo(file, params))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.layout}>
      <section className="panel">
        <h3>1 · 上传 MP4</h3>
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
          {videoUrl ? (
            <video
              className={`${styles.preview} ${styles.checker}`}
              src={videoUrl}
              controls
              muted
              playsInline
            />
          ) : (
            <p className={styles.dropHint}>点击选择 或 拖入 MP4<br /><span>≤ 50MB · 时长 ≤ 60s</span></p>
          )}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="video/mp4,video/*"
          hidden
          onChange={(e) => pickFile(e.target.files?.[0])}
        />
        {file && (
          <p className={styles.fileMeta}>
            <span className="mono">{file.name}</span>
            <span>{fmtBytes(file.size)}</span>
          </p>
        )}

        <h3 className={styles.sectionTitle}>2 · Sheet 参数</h3>
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
        </div>

        <div className={styles.actions}>
          <button type="button" className={styles.primaryBtn} disabled={!file || loading} onClick={handleCut}>
            {loading ? '处理中…' : '✂ 提取主体 → sprite sheet'}
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
            <h3>Sheet {result.width}×{result.height} · {result.frame_count} 帧 · {result.cols}×{result.rows} 网格</h3>
            <span className="tag">{result.fps_hint.toFixed(2)} fps</span>
            <span className={styles.meta}>{result.elapsed_ms}ms</span>
            <span className={styles.spring} />
            <a className={styles.primaryBtn} href={sheetUrl(result.job_id)} download>
              ⬇ sheet.png
            </a>
            <a className={styles.primaryBtn} href={framesZipUrl(result.job_id)} download>
              ⬇ frames.zip
            </a>
            <a className={styles.ghostBtn} href={framesJsonUrl(result.job_id)} target="_blank" rel="noreferrer">
              frames.json
            </a>
            <a className={styles.ghostBtn} href={previewApngUrl(result.job_id)} target="_blank" rel="noreferrer">
              预览 APNG
            </a>
            <a className={styles.ghostBtn} href={previewWebpUrl(result.job_id)} target="_blank" rel="noreferrer">
              预览 WebP
            </a>
          </div>
          <figure className={styles.gifFigure}>
            <img className={styles.checker} src={previewApngUrl(result.job_id)} alt="sprite sheet 预览" />
            <figcaption>棋盘格底显示透明区域；预览为 APNG 动画（首/中/尾 3 帧 8fps）</figcaption>
          </figure>
        </section>
      ) : (
        <section className="empty-card">
          <h3>Sprite Sheet 结果将显示在这里</h3>
          <p>算法：每帧独立色距背景估计 → 边界泛洪 → 仅最大连通域 → 全片统一画布（union bbox）→ 网格拼图 + frames.json 元数据 + 预览动画。适合游戏/网页 sprite 批量导入。</p>
        </section>
      )}
    </div>
  )
}