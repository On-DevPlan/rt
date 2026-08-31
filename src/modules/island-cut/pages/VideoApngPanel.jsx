import { useCallback, useEffect, useRef, useState } from 'react'
import {
  DEFAULT_PARAMS, compressFactorToPalette,
  cutVideo, apngUrl, previewUrl,
} from '../services/videoApngApi.js'
import { fmtSize } from '../utils/fmt.js'
import styles from './IslandCutPage.module.css'

const PARAM_FIELDS = [
  { key: 'fps',              label: '帧率',     min: 1,    max: 30,    step: 1, hint: '输出 APNG 帧率（源帧率更低时自动夹紧）' },
  { key: 'max_size',         label: '最长边',   min: 0,    max: 1024,  step: 16, hint: '0 = 不缩放；>0 时主体长边 = 该值' },
  { key: 'bg_tol',           label: 'BG容差',   min: 1,    max: 255,   step: 1, hint: '与背景色差异阈值；>水印最大差异才能吃掉水印' },
  { key: 'pad',              label: '留白',     min: 0,    max: 50,    step: 1, hint: '主体包围盒四周留白像素' },
  { key: 'max_duration_sec', label: '时长上限', min: 10,   max: 300,   step: 10, hint: '超过抛 413' },
  { key: 'max_frames',       label: '帧数上限', min: 60,   max: 1500,  step: 30, hint: '超过抛 413' },
]

const COMPRESS_MIN = 1
const COMPRESS_MAX = 20

function fmtBytes(n) {
  if (n > 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${Math.max(1, Math.round(n / 1024))} KB`
}

export default function VideoApngPanel() {
  const [file, setFile] = useState(null)
  const [videoUrl, setVideoUrl] = useState('')
  const [params, setParams] = useState(DEFAULT_PARAMS)
  const [compressFactor, setCompressFactor] = useState(4)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    const palette = compressFactorToPalette(compressFactor)
    setParams((p) => (p.use_palette === palette ? p : { ...p, use_palette: palette }))
  }, [compressFactor])

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

  const sizeInfo = result?.output_size_bytes != null ? fmtSize(result.output_size_bytes) : '—'
  const compressed = result?.compression_attempts > 1

  return (
    <div className={styles.layout}>
      <section className="panel">
        <h3>1 · 上传 MP4</h3>
        <div
          className={`${styles.dropzone}${dragging ? ` ${styles.dropzoneActive}` : ''}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false) }
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

        <h3 className={styles.sectionTitle}>2 · APNG 参数</h3>
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
          <label className={styles.paramRow} title="1x = 不压（真 RGBA）；2x+ = 调色板 256 色（约 1/3-1/4 体积）；更大压缩靠 fps 阶梯（自动）">
            <span className={styles.paramLabel}>压缩倍数</span>
            <input
              type="range"
              min={COMPRESS_MIN}
              max={COMPRESS_MAX}
              step={1}
              value={compressFactor}
              onChange={(e) => setCompressFactor(Number(e.target.value))}
            />
            <input
              className={styles.paramValue}
              type="number"
              min={COMPRESS_MIN}
              max={COMPRESS_MAX}
              step={1}
              value={compressFactor}
              onChange={(e) => setCompressFactor(Number(e.target.value))}
            />
          </label>
          <p className={styles.compressHint}>
            → 模式：{params.use_palette
              ? <><strong>调色板 256 色</strong>（tRNS alpha，透明渐变被量化）</>
              : <><strong>真 RGBA</strong>（保真无压缩）</>}
          </p>
        </div>

        <div className={styles.actions}>
          <button type="button" className={styles.primaryBtn} disabled={!file || loading} onClick={handleCut}>
            {loading ? '处理中…' : '✂ 提取主体 → APNG'}
          </button>
          <button type="button" className={styles.ghostBtn} onClick={() => { setParams(DEFAULT_PARAMS); setCompressFactor(4) }}>
            重置参数
          </button>
        </div>
        {error && <p className={styles.errorBox}>{error}</p>}
      </section>

      {result ? (
        <section className="panel">
          <div className="toolbar">
            <h3>APNG {result.width}×{result.height} · {result.frame_count} 帧</h3>
            <span className="tag">{params.use_palette ? 'palette' : 'rgba'}</span>
            {compressed && (
              <span className="tag" title={`压缩迭代 ${result.compression_attempts} 次`}>
                压缩 {result.compression_attempts}×
              </span>
            )}
            <span className={styles.meta}>最终 fps {result.final_fps.toFixed(2)} · {result.elapsed_ms}ms</span>
            <span className={styles.spring} />
            <strong className={styles.sizeBadge} title="输出文件大小">
              📦 {sizeInfo}
            </strong>
            <a className={styles.primaryBtn} href={apngUrl(result.job_id)} download="output.apng">
              ⬇ 下载 APNG
            </a>
            <a className={styles.ghostBtn} href={previewUrl(result.job_id)} target="_blank" rel="noreferrer">
              棋盘预览
            </a>
          </div>
          <figure className={styles.gifFigure}>
            <img className={styles.checker} src={apngUrl(result.job_id)} alt="生成的透明 APNG" />
            <figcaption>棋盘格底显示透明区域；{params.use_palette ? '256 色调色板' : '真 RGBA'}</figcaption>
          </figure>
        </section>
      ) : (
        <section className="empty-card">
          <h3>APNG 结果将显示在这里</h3>
          <p>算法：边框中位背景估计 → 每帧取最大连通岛屿 → 全帧统一裁剪 → NEAREST 缩放 → {params.use_palette ? '调色板' : '真 RGBA'} APNG。压缩倍数 ≥2 启用调色板（≈ 1/3-1/4 体积）。</p>
        </section>
      )}
    </div>
  )
}