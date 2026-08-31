import { useCallback, useEffect, useRef, useState } from 'react'
import { DEFAULT_PARAMS, cutVideo, gifUrl, previewUrl } from '../services/videoCutApi.js'
import styles from './IslandCutPage.module.css'

const PARAM_FIELDS = [
  { key: 'fps',              label: '帧率',     min: 1,    max: 30,    step: 1, hint: '输出 GIF 帧率（源帧率更低时自动夹紧）' },
  { key: 'max_size',         label: '最长边',   min: 0,    max: 1024,  step: 16, hint: '0 = 不缩放；>0 时主体长边 = 该值' },
  { key: 'bg_tol',           label: 'BG容差',   min: 1,    max: 255,   step: 1, hint: '与背景色差异阈值；>水印最大差异才能吃掉水印' },
  { key: 'pad',              label: '留白',     min: 0,    max: 50,    step: 1, hint: '主体包围盒四周留白像素' },
  { key: 'max_duration_sec', label: '时长上限', min: 10,   max: 300,   step: 10, hint: '超过抛 413' },
  { key: 'max_frames',       label: '帧数上限', min: 60,   max: 1500,  step: 30, hint: '超过抛 413' },
]

/** 体积上限独立输入（KB，空 = 不限制） */
function MaxOutputField({ value, onChange }) {
  return (
    <div className={styles.paramRow} title="输出文件超过该体积时自动降帧率重编码（fps/2, /4, /8 直到 1）；仍超限报 413">
      <span className={styles.paramLabel}>体积上限</span>
      <input
        className={styles.paramValue}
        style={{ gridColumn: '2 / -1' }}
        type="number"
        min={1}
        step={64}
        placeholder="KB，留空 = 不限制"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
      />
    </div>
  )
}

function fmtBytes(n) {
  if (n > 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${Math.max(1, Math.round(n / 1024))} KB`
}

export default function VideoGifPanel() {
  const [file, setFile] = useState(null)
  const [videoUrl, setVideoUrl] = useState('')
  const [params, setParams] = useState(DEFAULT_PARAMS)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  // 切换/卸载时回收 objectURL
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

        <h3 className={styles.sectionTitle}>2 · GIF 参数</h3>
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
          <MaxOutputField value={params.max_output_kb} onChange={(v) => setParam('max_output_kb', v)} />
        </div>

        <div className={styles.actions}>
          <button type="button" className={styles.primaryBtn} disabled={!file || loading} onClick={handleCut}>
            {loading ? '处理中…' : '✂ 提取主体 → GIF'}
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
            <h3>GIF {result.width}×{result.height} · {result.frame_count} 帧</h3>
            <span className="tag">{result.out_fps.toFixed(2)} fps</span>
            {result.compression_attempts > 1 && (
              <span className="tag" title={`为满足体积上限从 ${result.out_fps.toFixed(1)} fps 降帧重编了 ${result.compression_attempts - 1} 次`}>
                压缩 ×{result.compression_attempts} · {result.final_fps.toFixed(1)} fps
              </span>
            )}
            <span className={styles.meta}>源 {result.src_fps.toFixed(2)} fps · {(result.output_size_bytes / 1024).toFixed(0)} KB · {result.elapsed_ms}ms</span>
            <span className={styles.spring} />
            <a className={styles.primaryBtn} href={gifUrl(result.job_id)} download>
              ⬇ 下载 GIF
            </a>
            <a className={styles.ghostBtn} href={previewUrl(result.job_id)} target="_blank" rel="noreferrer">
              棋盘预览
            </a>
          </div>
          <figure className={styles.gifFigure}>
            <img className={styles.checker} src={gifUrl(result.job_id)} alt="生成的透明 GIF" />
            <figcaption>棋盘格底显示透明区域；GIF 是 disposal=2 防残影的循环图</figcaption>
          </figure>
        </section>
      ) : (
        <section className="empty-card">
          <h3>GIF 结果将显示在这里</h3>
          <p>算法：边框中位背景估计 → 每帧取最大连通岛屿 → 全帧统一裁剪 → NEAREST 缩放 → disposal=2 GIF。3 帧棋盘预览辅助检查透明边缘。</p>
        </section>
      )}
    </div>
  )
}