import { useState, useCallback } from 'react'
import styles from './EnrollmentPage.module.css'

const INITIAL_PARTICIPANTS = [
  { id: 1, name: '张明远', phone: '13812347621', email: 'zhangmy@mail.com', gender: 'male', status: 'confirmed', time: '05-08 14:32' },
  { id: 2, name: '李思琪', phone: '15954343348', email: 'lisq@mail.com', gender: 'female', status: 'confirmed', time: '05-09 09:15' },
  { id: 3, name: '王浩然', phone: '18623450092', email: 'wanghr@mail.com', gender: 'male', status: 'pending', time: '05-10 11:47' },
  { id: 4, name: '赵雨桐', phone: '17767895581', email: 'zhaoyt@mail.com', gender: 'female', status: 'cancelled', time: '05-10 16:03' },
]

const EVENT_INFO = {
  title: '2026 创意设计工作坊',
  date: '2026年6月15日',
  location: '科技园区 A栋 3F',
  capacity: 30,
}

const STATUS_MAP = {
  confirmed: { label: '已确认', className: styles.tagConfirmed },
  pending: { label: '待确认', className: styles.tagPending },
  cancelled: { label: '已取消', className: styles.tagCancelled },
}

let nextId = 5

function Avatar({ name, gender }) {
  const initial = name.charAt(0)
  const cls = gender === 'female' ? styles.participantAvatarFemale : styles.participantAvatarMale
  return (
    <div className={`${styles.participantAvatar} ${cls}`}>
      {initial}
    </div>
  )
}

export default function EnrollmentPage() {
  const [participants, setParticipants] = useState(INITIAL_PARTICIPANTS)
  const [showSuccess, setShowSuccess] = useState(false)
  const [lastSubmitted, setLastSubmitted] = useState('')
  const [errors, setErrors] = useState({})

  const [form, setForm] = useState({
    name: '',
    phone: '',
    email: '',
    gender: '',
    remark: '',
    agree: false,
  })

  const confirmed = participants.filter(p => p.status === 'confirmed').length
  const pending = participants.filter(p => p.status === 'pending').length
  const cancelled = participants.filter(p => p.status === 'cancelled').length
  const fillPercent = Math.round((confirmed / EVENT_INFO.capacity) * 100)

  const updateField = useCallback((field, value) => {
    setForm(prev => ({ ...prev, [field]: value }))
    setErrors(prev => {
      if (!prev[field]) return prev
      const next = { ...prev }
      delete next[field]
      return next
    })
  }, [])

  const validate = useCallback(() => {
    const errs = {}
    if (!form.name.trim()) errs.name = '请输入姓名'
    if (!form.phone.trim()) errs.phone = '请输入手机号'
    else if (!/^1[3-9]\d{9}$/.test(form.phone.trim())) errs.phone = '手机号格式不正确'
    if (!form.email.trim()) errs.email = '请输入邮箱'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) errs.email = '邮箱格式不正确'
    if (!form.gender) errs.gender = '请选择性别'
    if (!form.agree) errs.agree = '请同意条款'
    return errs
  }, [form])

  const handleSubmit = useCallback(() => {
    const errs = validate()
    if (Object.keys(errs).length > 0) {
      setErrors(errs)
      return
    }

    const now = new Date()
    const timeStr = `${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`

    const newParticipant = {
      id: nextId++,
      name: form.name.trim(),
      phone: form.phone.trim(),
      email: form.email.trim(),
      gender: form.gender,
      status: 'pending',
      time: timeStr,
    }

    setParticipants(prev => [newParticipant, ...prev])
    setLastSubmitted(form.name.trim())
    setShowSuccess(true)
    setForm({ name: '', phone: '', email: '', gender: '', remark: '', agree: false })
    setErrors({})
  }, [form, validate])

  const handleRemove = useCallback((id) => {
    setParticipants(prev => prev.filter(p => p.id !== id))
  }, [])

  const handleCloseSuccess = useCallback(() => {
    setShowSuccess(false)
  }, [])

  return (
    <div className={styles.root}>
      {/* Hero Banner */}
      <div className={styles.heroBanner}>
        <div className={styles.heroBannerDecor}>
          <div className={styles.heroDecorCircle} />
          <div className={styles.heroDecorCircle} />
          <div className={styles.heroDecorCircle} />
          <div className={styles.heroDecorLine} />
          <div className={styles.heroDecorLine} />
        </div>
        <div className={styles.heroBannerContent}>
          <div className={styles.heroTag}>
            <span className={styles.heroTagDot} />
            报名进行中
          </div>
          <h1 className={styles.heroTitle}>{EVENT_INFO.title}</h1>
          <p className={styles.heroDesc}>
            填写以下信息完成报名，提交后将进入待确认状态。请留意短信或邮件通知。
          </p>
          <div className={styles.heroInfoRow}>
            <div className={styles.heroInfoItem}>
              <div className={styles.heroInfoIcon}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.7)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                  <line x1="16" y1="2" x2="16" y2="6" />
                  <line x1="8" y1="2" x2="8" y2="6" />
                  <line x1="3" y1="10" x2="21" y2="10" />
                </svg>
              </div>
              <div className={styles.heroInfoText}>
                <span className={styles.heroInfoLabel}>日期</span>
                <span className={styles.heroInfoValue}>{EVENT_INFO.date}</span>
              </div>
            </div>
            <div className={styles.heroInfoItem}>
              <div className={styles.heroInfoIcon}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.7)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                  <circle cx="12" cy="10" r="3" />
                </svg>
              </div>
              <div className={styles.heroInfoText}>
                <span className={styles.heroInfoLabel}>地点</span>
                <span className={styles.heroInfoValue}>{EVENT_INFO.location}</span>
              </div>
            </div>
            <div className={styles.heroInfoItem}>
              <div className={styles.heroInfoIcon}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.7)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              </div>
              <div className={styles.heroInfoText}>
                <span className={styles.heroInfoLabel}>名额</span>
                <span className={styles.heroInfoValue}>{EVENT_INFO.capacity} 人</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className={styles.container}>
        {/* Summary Strip */}
        <div className={styles.summaryStrip}>
          <div className={styles.summaryCell}>
            <div className={styles.summaryValue}>{confirmed}<span className={styles.summaryUnit}>/{EVENT_INFO.capacity}</span></div>
            <div className={styles.summaryLabel}>已确认</div>
          </div>
          <div className={styles.summaryCell}>
            <div className={styles.summaryValue}>{pending}</div>
            <div className={styles.summaryLabel}>待确认</div>
          </div>
          <div className={styles.summaryCell}>
            <div className={styles.summaryValue}>{fillPercent}<span className={styles.summaryUnit}>%</span></div>
            <div className={styles.summaryLabel}>完成率</div>
          </div>
        </div>

        {/* Registration Form */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>
            <span className={styles.sectionTitleIcon}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <line x1="19" y1="8" x2="19" y2="14" />
                <line x1="22" y1="11" x2="16" y2="11" />
              </svg>
            </span>
            报名信息
          </h2>

          <div className={styles.fieldGroup}>
            <div className={styles.field}>
              <label className={styles.fieldLabel}>姓名<span className={styles.fieldLabelRequired}>*</span></label>
              <input className={`${styles.fieldInput} ${errors.name ? styles.hasError : ''}`} type="text" placeholder="请输入姓名" value={form.name} onChange={e => updateField('name', e.target.value)} />
              {errors.name && <span className={styles.fieldError}>{errors.name}</span>}
            </div>
            <div className={styles.field}>
              <label className={styles.fieldLabel}>手机号<span className={styles.fieldLabelRequired}>*</span></label>
              <input className={`${styles.fieldInput} ${errors.phone ? styles.hasError : ''}`} type="tel" placeholder="请输入手机号" value={form.phone} onChange={e => updateField('phone', e.target.value)} />
              {errors.phone && <span className={styles.fieldError}>{errors.phone}</span>}
            </div>
            <div className={styles.field}>
              <label className={styles.fieldLabel}>邮箱<span className={styles.fieldLabelRequired}>*</span></label>
              <input className={`${styles.fieldInput} ${errors.email ? styles.hasError : ''}`} type="email" placeholder="example@mail.com" value={form.email} onChange={e => updateField('email', e.target.value)} />
              {errors.email && <span className={styles.fieldError}>{errors.email}</span>}
            </div>
            <div className={styles.field}>
              <label className={styles.fieldLabel}>性别<span className={styles.fieldLabelRequired}>*</span></label>
              <div className={styles.radioGroup}>
                <div className={styles.radioOption}>
                  <input className={styles.radioOptionInput} type="radio" name="gender" id="gender-male" value="male" checked={form.gender === 'male'} onChange={() => updateField('gender', 'male')} />
                  <label className={styles.radioOptionLabel} htmlFor="gender-male">男</label>
                </div>
                <div className={styles.radioOption}>
                  <input className={styles.radioOptionInput} type="radio" name="gender" id="gender-female" value="female" checked={form.gender === 'female'} onChange={() => updateField('gender', 'female')} />
                  <label className={styles.radioOptionLabel} htmlFor="gender-female">女</label>
                </div>
              </div>
              {errors.gender && <span className={styles.fieldError}>{errors.gender}</span>}
            </div>

            <div className={styles.fieldDivider} />

            <div className={`${styles.field} ${styles.fieldFull}`}>
              <label className={styles.fieldLabel}>备注</label>
              <textarea className={styles.fieldTextarea} placeholder="如有特殊需求请在此说明" value={form.remark} onChange={e => updateField('remark', e.target.value)} />
            </div>
            <div className={`${styles.field} ${styles.fieldFull}`}>
              <label className={styles.checkboxField}>
                <input className={styles.checkboxInput} type="checkbox" checked={form.agree} onChange={e => updateField('agree', e.target.checked)} />
                <span className={styles.checkboxLabel}>我已阅读并同意《活动报名须知》和《隐私政策》</span>
              </label>
              {errors.agree && <span className={styles.fieldError}>{errors.agree}</span>}
            </div>
          </div>

          <div className={styles.actions}>
            <button className={styles.btnPrimary} onClick={handleSubmit}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              提交报名
            </button>
            <button className={styles.btnSecondary} onClick={() => { setForm({ name: '', phone: '', email: '', gender: '', remark: '', agree: false }); setErrors({}) }}>
              重置
            </button>
          </div>
        </section>

        {/* Participant List */}
        <section className={styles.section}>
          <div className={styles.tableHeader}>
            <h2 className={styles.sectionTitle} style={{ margin: 0 }}>
              <span className={styles.sectionTitleIcon}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              </span>
              报名列表
            </h2>
            <span className={styles.tableCount}>共 {participants.length} 人</span>
          </div>

          <div className={styles.progressWrap}>
            <div className={styles.progressHeader}>
              <span className={styles.progressLabel}>报名进度</span>
              <span className={styles.progressPercent}>{confirmed}/{EVENT_INFO.capacity} 已确认</span>
            </div>
            <div className={styles.progressTrack}>
              <div className={styles.progressFill} style={{ width: `${fillPercent}%` }} />
            </div>
          </div>

          <div className={styles.statsBar}>
            <div className={styles.statCard}>
              <div className={`${styles.statIcon} ${styles.statIconConfirmed}`}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
              </div>
              <div className={styles.statContent}>
                <span className={styles.statValue}>{confirmed}</span>
                <span className={styles.statLabel}>已确认</span>
              </div>
            </div>
            <div className={styles.statCard}>
              <div className={`${styles.statIcon} ${styles.statIconPending}`}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>
              </div>
              <div className={styles.statContent}>
                <span className={styles.statValue}>{pending}</span>
                <span className={styles.statLabel}>待确认</span>
              </div>
            </div>
            <div className={styles.statCard}>
              <div className={`${styles.statIcon} ${styles.statIconCancelled}`}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" /></svg>
              </div>
              <div className={styles.statContent}>
                <span className={styles.statValue}>{cancelled}</span>
                <span className={styles.statLabel}>已取消</span>
              </div>
            </div>
          </div>

          {participants.length === 0 ? (
            <div className={styles.emptyState}>
              <div className={styles.emptyStateIcon}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <line x1="19" y1="8" x2="19" y2="14" />
                  <line x1="22" y1="11" x2="16" y2="11" />
                </svg>
              </div>
              <p className={styles.emptyStateText}>暂无报名记录</p>
            </div>
          ) : (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>姓名</th>
                  <th>手机号</th>
                  <th>报名时间</th>
                  <th>状态</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {participants.map(p => {
                  const statusInfo = STATUS_MAP[p.status]
                  return (
                    <tr key={p.id} className={styles.tableRow}>
                      <td>
                        <div className={styles.participantCell}>
                          <Avatar name={p.name} gender={p.gender} />
                          <div>
                            <div className={styles.participantName}>{p.name}</div>
                            <div className={styles.participantEmail}>{p.email}</div>
                          </div>
                        </div>
                      </td>
                      <td className={styles.participantPhone}>{p.phone.slice(0, 3)}****{p.phone.slice(-4)}</td>
                      <td className={styles.participantTime}>{p.time}</td>
                      <td>
                        <span className={`${styles.tag} ${statusInfo.className}`}>
                          <span className={styles.tagDot} />
                          {statusInfo.label}
                        </span>
                      </td>
                      <td>
                        <button className={styles.btnDelete} onClick={() => handleRemove(p.id)}>移除</button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </section>

        <div className={styles.footerNote}>
          <div className={styles.footerNoteDivider} />
          报名信息仅用于本次活动，我们将严格保护您的隐私
        </div>
      </div>

      {/* Success Overlay */}
      {showSuccess && (
        <div className={styles.successOverlay} onClick={handleCloseSuccess}>
          <div className={styles.successCard} onClick={e => e.stopPropagation()}>
            <div className={styles.successIcon}>
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <h3 className={styles.successTitle}>报名成功</h3>
            <p className={styles.successDesc}>
              {lastSubmitted}，您的报名信息已提交，当前状态为「待确认」。<br />
              请留意手机短信或邮件通知。
            </p>
            <div className={styles.successActions}>
              <button className={styles.btnPrimary} onClick={handleCloseSuccess}>我知道了</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
