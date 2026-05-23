import { useState, useMemo, useCallback } from 'react'
import { useDocumentTitle } from '../../../framework/hooks/useDocumentTitle.js'
import styles from './CompetitionPage.module.css'

const COMPETITION = {
  name: '2026 全国创新创业大赛',
  subtitle: '由科创基金会 · 数字经济产业联盟联合主办，聚焦前沿科技、文化创意与可持续发展的青年创业舞台。',
  startDate: '2026.06.18',
  endDate: '2026.06.22',
  totalDays: 5,
  fee: 299,
  capacity: 500,
  registered: 327,
  totalPrize: 88,
  tags: ['官方主办', '全国赛事', '青年专场', '免费住宿'],
}

const ADDRESS = {
  title: '杭州国际博览中心 · 主会场',
  full: '浙江省杭州市萧山区奔竞大道 353 号 G20 主会场 3 号厅',
  metro: '地铁 7 号线 国博中心站 A 出口，步行约 4 分钟',
  parking: 'P1 / P2 地下停车场（每小时 8 元，每日封顶 50 元）',
  shuttle: '萧山机场专线 09:00 – 18:00 半小时一班',
  contact: '组委会联系电话 0571-8888-6688',
}

const RULES = [
  { title: '参赛资格', text: '面向 18 ~ 35 周岁创业者、大学生及科研团队，单人或团队（1-5 人）皆可报名。' },
  { title: '赛程安排', text: '初赛（线上路演）→ 复赛（实地答辩）→ 决赛（导师 1v1 + 公开赛）三阶段，共历时五天。' },
  { title: '作品要求', text: '提交完整的商业计划书与原型/Demo 视频（≤ 8 分钟），鼓励真实可落地的早期项目。' },
  { title: '评审维度', text: '创新性 30% / 技术可行性 25% / 商业模式 25% / 团队执行力 20%。' },
  { title: '知识产权', text: '所有参赛作品归参赛者本人所有，主办方仅享有宣传、推广等非商业使用权利。' },
  { title: '违规处理', text: '存在抄袭、虚假项目或代为答辩行为，将直接取消参赛资格并通报全行业。' },
]

const PRIZES = [
  { rank: 1, label: '一等奖', name: '金奖（1 名）', desc: '奖杯 · 创投基金对接 · 央媒专访', amount: 30 },
  { rank: 2, label: '二等奖', name: '银奖（2 名）', desc: '奖杯 · 头部加速器入营资格', amount: 15 },
  { rank: 3, label: '三等奖', name: '铜奖（3 名）', desc: '奖杯 · 一线导师全程辅导半年', amount: 6 },
  { rank: 4, label: '入围奖', name: '入围奖（10 名）', desc: '奖牌 · 行业资源对接券', amount: 1 },
]

const PRIZE_USAGE = [
  { title: '项目落地资金（50%）', text: '由组委会托管账户分期发放，定向用于产品研发、原型试产及供应链启动。' },
  { title: '团队运营补贴（25%）', text: '用于支付获奖团队核心成员未来 6 个月的基础生活补助与差旅。' },
  { title: '品牌推广（15%）', text: '统一安排在官方渠道及合作媒体进行 PR 投放，并制作获奖项目专题片。' },
  { title: '导师与顾问服务费（10%）', text: '聘请创投、法务、税务、PR 等专家，为获奖团队提供 360° 陪跑服务。' },
]

const TIMELINE = [
  { date: '2026-05-20', title: '报名通道正式开启', text: '官方报名系统已全面上线，支持团队批量提交参赛材料，可随时修改至 06-10。', isNew: true },
  { date: '2026-05-15', title: '主办方阵容公布', text: '清华长三角研究院、阿里达摩院、红杉中国成长基金等机构正式加入赛事合作矩阵。', isNew: true },
  { date: '2026-04-28', title: '奖金池提升至 88 万元', text: '在原有 60 万奖金基础上新增「特别支持基金」28 万元，覆盖更广的入围团队。' },
  { date: '2026-04-10', title: '组委会成立暨筹备启动', text: '由 8 家产业机构联合发起，确定本届赛事主题：「面向 AI 时代的青年创业」。' },
]

const PROVINCES = {
  beijing: {
    label: '北京市',
    cities: {
      beijing_city: {
        label: '北京城区',
        counties: ['朝阳区', '海淀区', '东城区', '西城区', '丰台区', '通州区'],
      },
    },
  },
  shanghai: {
    label: '上海市',
    cities: {
      shanghai_city: {
        label: '上海城区',
        counties: ['浦东新区', '徐汇区', '黄浦区', '静安区', '长宁区', '虹口区'],
      },
    },
  },
  zhejiang: {
    label: '浙江省',
    cities: {
      hangzhou: {
        label: '杭州市',
        counties: ['西湖区', '上城区', '拱墅区', '滨江区', '萧山区', '余杭区', '临平区'],
      },
      ningbo: {
        label: '宁波市',
        counties: ['鄞州区', '海曙区', '江北区', '北仑区', '镇海区', '奉化区'],
      },
      wenzhou: {
        label: '温州市',
        counties: ['鹿城区', '龙湾区', '瓯海区', '永嘉县', '苍南县', '乐清市'],
      },
    },
  },
  jiangsu: {
    label: '江苏省',
    cities: {
      nanjing: {
        label: '南京市',
        counties: ['玄武区', '秦淮区', '建邺区', '鼓楼区', '雨花台区', '江宁区'],
      },
      suzhou: {
        label: '苏州市',
        counties: ['姑苏区', '吴中区', '相城区', '工业园区', '高新区', '昆山市'],
      },
    },
  },
  guangdong: {
    label: '广东省',
    cities: {
      guangzhou: {
        label: '广州市',
        counties: ['天河区', '海珠区', '越秀区', '荔湾区', '番禺区', '黄埔区'],
      },
      shenzhen: {
        label: '深圳市',
        counties: ['福田区', '罗湖区', '南山区', '宝安区', '龙岗区', '龙华区'],
      },
    },
  },
  sichuan: {
    label: '四川省',
    cities: {
      chengdu: {
        label: '成都市',
        counties: ['锦江区', '青羊区', '武侯区', '高新区', '天府新区', '双流区'],
      },
    },
  },
}

const INDUSTRIES = [
  '互联网 / AI',
  '金融科技',
  '教育培训',
  '医疗健康',
  '智能制造',
  '消费零售',
  '文化创意',
  '咨询服务',
  '新能源',
  '现代农业',
  '物流供应链',
  '其他',
]

const TABS = [
  { id: 'rules', label: '比赛规则', count: RULES.length },
  { id: 'prize', label: '奖金说明', count: PRIZES.length },
  { id: 'timeline', label: '赛事动态', count: TIMELINE.filter(i => i.isNew).length },
  { id: 'address', label: '比赛地址', count: null },
]

function IconHash() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="4" y1="9" x2="20" y2="9" /><line x1="4" y1="15" x2="20" y2="15" />
      <line x1="10" y1="3" x2="8" y2="21" /><line x1="16" y1="3" x2="14" y2="21" />
    </svg>
  )
}
function IconPin() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" /><circle cx="12" cy="10" r="3" />
    </svg>
  )
}
function IconCalendar() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  )
}
function IconWallet() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12V7H5a2 2 0 010-4h14v4" /><path d="M3 5v14a2 2 0 002 2h16v-5" /><path d="M18 12a2 2 0 100 4h4v-4z" />
    </svg>
  )
}
function IconUsers() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" /><circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 00-3-3.87" /><path d="M16 3.13a4 4 0 010 7.75" />
    </svg>
  )
}
function IconTrophy() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 9H4.5a2.5 2.5 0 010-5H6" /><path d="M18 9h1.5a2.5 2.5 0 000-5H18" />
      <path d="M4 22h16" /><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22" />
      <path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22" />
      <path d="M18 2H6v7a6 6 0 0012 0V2z" />
    </svg>
  )
}
function IconCheck() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 6L9 17l-5-5" />
    </svg>
  )
}
function IconArrow() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
    </svg>
  )
}
function IconMap() {
  return (
    <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
      <line x1="8" y1="2" x2="8" y2="18" /><line x1="16" y1="6" x2="16" y2="22" />
    </svg>
  )
}

const PRIZE_RANK_CLASS = {
  1: styles.prizeRank1,
  2: styles.prizeRank2,
  3: styles.prizeRank3,
  4: styles.prizeRankN,
}

export default function CompetitionPage() {
  useDocumentTitle('赛事报名')

  const [activeTab, setActiveTab] = useState('rules')
  const [registered, setRegistered] = useState(COMPETITION.registered)
  const [showSuccess, setShowSuccess] = useState(false)
  const [lastOrder, setLastOrder] = useState(null)
  const [errors, setErrors] = useState({})

  const [form, setForm] = useState({
    name: '',
    phone: '',
    province: '',
    city: '',
    county: '',
    industries: [],
    agree: false,
  })

  const cityOptions = useMemo(() => {
    if (!form.province) return {}
    return PROVINCES[form.province]?.cities || {}
  }, [form.province])

  const countyOptions = useMemo(() => {
    if (!form.province || !form.city) return []
    return PROVINCES[form.province]?.cities?.[form.city]?.counties || []
  }, [form.province, form.city])

  const updateField = useCallback((field, value) => {
    setForm(prev => ({ ...prev, [field]: value }))
    setErrors(prev => ({ ...prev, [field]: undefined }))
  }, [])

  const onProvince = useCallback((v) => {
    setForm(prev => ({ ...prev, province: v, city: '', county: '' }))
    setErrors(prev => ({ ...prev, province: undefined, city: undefined, county: undefined }))
  }, [])

  const onCity = useCallback((v) => {
    setForm(prev => ({ ...prev, city: v, county: '' }))
    setErrors(prev => ({ ...prev, city: undefined, county: undefined }))
  }, [])

  const toggleIndustry = useCallback((name) => {
    setForm(prev => {
      const exists = prev.industries.includes(name)
      const next = exists ? prev.industries.filter(i => i !== name) : [...prev.industries, name]
      return { ...prev, industries: next }
    })
    setErrors(prev => ({ ...prev, industries: undefined }))
  }, [])

  const validate = () => {
    const e = {}
    if (!form.name.trim()) e.name = '请输入您的姓名'
    if (!form.phone.trim()) e.phone = '请输入手机号码'
    else if (!/^1[3-9]\d{9}$/.test(form.phone.trim())) e.phone = '手机号码格式不正确'
    if (!form.province) e.province = '请选择省份'
    if (!form.city) e.city = '请选择城市'
    if (!form.county) e.county = '请选择区/县'
    if (form.industries.length === 0) e.industries = '请至少选择一个行业'
    if (!form.agree) e.agree = '请阅读并同意赛事条款'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const onSubmit = (ev) => {
    ev.preventDefault()
    if (!validate()) return

    const orderId = 'CC' + Date.now().toString().slice(-8)
    const provinceLabel = PROVINCES[form.province]?.label || ''
    const cityLabel = PROVINCES[form.province]?.cities?.[form.city]?.label || ''
    const full = `${provinceLabel} / ${cityLabel} / ${form.county}`

    setLastOrder({
      orderId,
      name: form.name,
      phone: form.phone,
      location: full,
      industries: form.industries,
      fee: COMPETITION.fee,
    })
    setRegistered(prev => prev + 1)
    setShowSuccess(true)
  }

  const closeSuccess = () => {
    setShowSuccess(false)
    setForm({ name: '', phone: '', province: '', city: '', county: '', industries: [], agree: false })
  }

  const fillPercent = Math.round((registered / COMPETITION.capacity) * 100)

  return (
    <div className={styles.root}>
      <div className={styles.heroBanner}>
        <div className={styles.heroDecor} />
        <div className={styles.heroBannerContent}>
          <div className={styles.heroTopRow}>
            <div className={styles.heroLeft}>
              <div className={styles.heroTag}>
                <span className={styles.heroTagDot} />
                报名进行中 · 截止 06-10
              </div>
              <h1 className={styles.heroTitle}>{COMPETITION.name}</h1>
              <p className={styles.heroSubtitle}>{COMPETITION.subtitle}</p>
              <div className={styles.heroBadgeRow}>
                {COMPETITION.tags.map(t => (
                  <span key={t} className={styles.heroBadge}>{t}</span>
                ))}
              </div>
            </div>
            <div className={styles.heroStatsCard}>
              <div className={styles.heroStatsCardTitle}>赛事数据</div>
              <div className={styles.heroStatsRow}>
                <div className={styles.heroStat}>
                  <div className={styles.heroStatValue}>{registered}</div>
                  <div className={styles.heroStatLabel}>已报名</div>
                </div>
                <div className={styles.heroStat}>
                  <div className={styles.heroStatValue}>{COMPETITION.totalDays}</div>
                  <div className={styles.heroStatLabel}>赛程天数</div>
                </div>
              </div>
              <div className={styles.heroPrize}>
                <div className={styles.heroPrizeLabel}>总奖金池</div>
                <div className={styles.heroPrizeValue}>
                  ¥{COMPETITION.totalPrize}
                  <span className={styles.heroPrizeUnit}>万元</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className={styles.container}>
        <div className={styles.infoStrip}>
          <div className={`${styles.infoStripItem} ${styles.infoStripDivider}`}>
            <div className={styles.infoStripIcon}><IconPin /></div>
            <div className={styles.infoStripText}>
              <div className={styles.infoStripLabel}>比赛地点</div>
              <div className={styles.infoStripValue}>杭州 · 国际博览中心</div>
              <div className={styles.infoStripSub}>主会场 3 号厅</div>
            </div>
          </div>
          <div className={`${styles.infoStripItem} ${styles.infoStripDivider}`}>
            <div className={styles.infoStripIcon}><IconCalendar /></div>
            <div className={styles.infoStripText}>
              <div className={styles.infoStripLabel}>赛程时间</div>
              <div className={styles.infoStripValue}>{COMPETITION.startDate} – {COMPETITION.endDate}</div>
              <div className={styles.infoStripSub}>共 {COMPETITION.totalDays} 天</div>
            </div>
          </div>
          <div className={`${styles.infoStripItem} ${styles.infoStripDivider}`}>
            <div className={styles.infoStripIcon}><IconWallet /></div>
            <div className={styles.infoStripText}>
              <div className={styles.infoStripLabel}>报名金额</div>
              <div className={styles.infoStripValue}>¥{COMPETITION.fee}</div>
              <div className={styles.infoStripSub}>含资料 / 餐饮 / 周边</div>
            </div>
          </div>
          <div className={styles.infoStripItem}>
            <div className={styles.infoStripIcon}><IconUsers /></div>
            <div className={styles.infoStripText}>
              <div className={styles.infoStripLabel}>名额规模</div>
              <div className={styles.infoStripValue}>{registered} / {COMPETITION.capacity}</div>
              <div className={styles.infoStripSub}>已完成 {fillPercent}%</div>
            </div>
          </div>
        </div>

        <div className={styles.contentGrid}>
          <div className={styles.tabsCard}>
            <div className={styles.tabsHeader}>
              {TABS.map(tab => (
                <button
                  key={tab.id}
                  type="button"
                  className={`${styles.tab} ${activeTab === tab.id ? styles.tabActive : ''}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                  {tab.count !== null && <span className={styles.tabBadge}>{tab.count}</span>}
                </button>
              ))}
            </div>

            {activeTab === 'rules' && (
              <div className={styles.tabPanel}>
                <div className={styles.ruleList}>
                  {RULES.map((r, idx) => (
                    <div key={r.title} className={styles.ruleItem}>
                      <div className={styles.ruleNumber}>{idx + 1}</div>
                      <div className={styles.ruleContent}>
                        <h4 className={styles.ruleTitle}>{r.title}</h4>
                        <p className={styles.ruleText}>{r.text}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === 'prize' && (
              <div className={styles.tabPanel}>
                <div className={styles.prizeIntro}>
                  <div className={styles.prizeIntroIcon}><IconTrophy /></div>
                  <div>
                    <h4 className={styles.prizeIntroTitle}>总奖金 88 万元 + 创投基金对接</h4>
                    <p className={styles.prizeIntroText}>覆盖奖金、孵化、品牌曝光与导师陪跑，全方位扶持获奖团队真正落地。</p>
                  </div>
                </div>
                <div className={styles.prizeList}>
                  {PRIZES.map(p => (
                    <div key={p.label} className={styles.prizeItem}>
                      <div className={`${styles.prizeRank} ${PRIZE_RANK_CLASS[p.rank]}`}>{p.label.charAt(0)}</div>
                      <div className={styles.prizeInfo}>
                        <h4 className={styles.prizeName}>{p.name}</h4>
                        <div className={styles.prizeDesc}>{p.desc}</div>
                      </div>
                      <div className={styles.prizeAmount}>
                        ¥{p.amount}<span className={styles.prizeUnit}>万</span>
                      </div>
                    </div>
                  ))}
                </div>
                <h4 className={styles.ruleTitle} style={{ marginTop: 24, marginBottom: 12 }}>奖金使用说明</h4>
                <div className={styles.ruleList}>
                  {PRIZE_USAGE.map((u, idx) => (
                    <div key={u.title} className={styles.ruleItem}>
                      <div className={styles.ruleNumber}>{idx + 1}</div>
                      <div className={styles.ruleContent}>
                        <h4 className={styles.ruleTitle}>{u.title}</h4>
                        <p className={styles.ruleText}>{u.text}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === 'timeline' && (
              <div className={styles.tabPanel}>
                <div className={styles.timeline}>
                  {TIMELINE.map((t, idx) => (
                    <div key={t.date + t.title} className={styles.timelineItem}>
                      <div className={`${styles.timelineDot} ${idx >= 2 ? styles.timelineDotInactive : ''}`} />
                      <div className={styles.timelineDate}>{t.date}</div>
                      <h4 className={styles.timelineTitle}>
                        {t.title}
                        {t.isNew && <span className={styles.timelineNew}>New</span>}
                      </h4>
                      <p className={styles.timelineText}>{t.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === 'address' && (
              <div className={styles.tabPanel}>
                <div className={styles.addressMap}>
                  <div className={styles.addressMapVisual}><IconMap /></div>
                  <div className={styles.addressDetails}>
                    <h3 className={styles.addressTitle}>{ADDRESS.title}</h3>
                    <p className={styles.addressFull}>{ADDRESS.full}</p>
                    <div className={styles.addressInfo}>
                      <div className={styles.addressInfoItem}>
                        <span className={styles.addressInfoLabel}>地铁</span>
                        <span className={styles.addressInfoValue}>{ADDRESS.metro}</span>
                      </div>
                      <div className={styles.addressInfoItem}>
                        <span className={styles.addressInfoLabel}>停车</span>
                        <span className={styles.addressInfoValue}>{ADDRESS.parking}</span>
                      </div>
                      <div className={styles.addressInfoItem}>
                        <span className={styles.addressInfoLabel}>接驳</span>
                        <span className={styles.addressInfoValue}>{ADDRESS.shuttle}</span>
                      </div>
                      <div className={styles.addressInfoItem}>
                        <span className={styles.addressInfoLabel}>联系</span>
                        <span className={styles.addressInfoValue}>{ADDRESS.contact}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          <form className={styles.formCard} onSubmit={onSubmit} noValidate>
            <div className={styles.formCardHeader}>
              <h3 className={styles.formCardTitle}>立即报名</h3>
              <p className={styles.formCardDesc}>名额有限，先报先得，截止 06-10 24:00。</p>
            </div>

            <div className={styles.formCardFeeRow}>
              <span className={styles.formCardFeeLabel}>报名费用</span>
              <div>
                <span className={styles.formCardFeeValue}>¥{COMPETITION.fee}</span>
                <span className={styles.formCardFeeUnit}> /人</span>
              </div>
            </div>

            <div className={styles.field}>
              <label className={styles.fieldLabel}>
                姓名<span className={styles.fieldLabelRequired}>*</span>
              </label>
              <input
                type="text"
                className={`${styles.fieldInput} ${errors.name ? styles.hasError : ''}`}
                placeholder="请输入真实姓名"
                value={form.name}
                onChange={e => updateField('name', e.target.value)}
                maxLength={20}
              />
              {errors.name && <span className={styles.fieldError}>{errors.name}</span>}
            </div>

            <div className={styles.field}>
              <label className={styles.fieldLabel}>
                手机号码<span className={styles.fieldLabelRequired}>*</span>
              </label>
              <input
                type="tel"
                className={`${styles.fieldInput} ${errors.phone ? styles.hasError : ''}`}
                placeholder="11 位手机号码"
                value={form.phone}
                onChange={e => updateField('phone', e.target.value)}
                maxLength={11}
              />
              {errors.phone && <span className={styles.fieldError}>{errors.phone}</span>}
            </div>

            <div className={styles.field}>
              <label className={styles.fieldLabel}>
                所在地区<span className={styles.fieldLabelRequired}>*</span>
              </label>
              <div className={styles.cascaderRow}>
                <select
                  className={`${styles.cascaderSelect} ${errors.province ? styles.hasError : ''}`}
                  value={form.province}
                  onChange={e => onProvince(e.target.value)}
                >
                  <option value="">省份</option>
                  {Object.entries(PROVINCES).map(([key, p]) => (
                    <option key={key} value={key}>{p.label}</option>
                  ))}
                </select>
                <select
                  className={`${styles.cascaderSelect} ${errors.city ? styles.hasError : ''}`}
                  value={form.city}
                  onChange={e => onCity(e.target.value)}
                  disabled={!form.province}
                >
                  <option value="">城市</option>
                  {Object.entries(cityOptions).map(([key, c]) => (
                    <option key={key} value={key}>{c.label}</option>
                  ))}
                </select>
                <select
                  className={`${styles.cascaderSelect} ${errors.county ? styles.hasError : ''}`}
                  value={form.county}
                  onChange={e => updateField('county', e.target.value)}
                  disabled={!form.city}
                >
                  <option value="">区/县</option>
                  {countyOptions.map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
              {(errors.province || errors.city || errors.county) && (
                <span className={styles.fieldError}>
                  {errors.province || errors.city || errors.county}
                </span>
              )}
            </div>

            <div className={styles.field}>
              <label className={styles.fieldLabel}>
                所在行业<span className={styles.fieldLabelRequired}>*</span>
                <span style={{ fontSize: 11, fontWeight: 500, color: '#a39e97', marginLeft: 6 }}>
                  可多选 · 已选 {form.industries.length}
                </span>
              </label>
              <div className={styles.industryGrid}>
                {INDUSTRIES.map(ind => {
                  const active = form.industries.includes(ind)
                  return (
                    <button
                      key={ind}
                      type="button"
                      className={`${styles.industryChip} ${active ? styles.industryChipActive : ''}`}
                      onClick={() => toggleIndustry(ind)}
                    >
                      {ind}
                    </button>
                  )
                })}
              </div>
              {errors.industries
                ? <span className={styles.fieldError}>{errors.industries}</span>
                : <span className={styles.industryHint}>选择最贴近您项目的方向，便于赛区分配</span>}
            </div>

            <label className={styles.agreeField}>
              <input
                type="checkbox"
                className={styles.checkboxInput}
                checked={form.agree}
                onChange={e => updateField('agree', e.target.checked)}
              />
              <span className={styles.checkboxText}>
                我已阅读并同意 <span className={styles.checkboxLink}>《赛事参与条款》</span> 与 <span className={styles.checkboxLink}>《隐私协议》</span>
                {errors.agree && <span className={styles.fieldError} style={{ display: 'block', marginTop: 4 }}>{errors.agree}</span>}
              </span>
            </label>

            <button type="submit" className={styles.submitBtn}>
              立即报名 · ¥{COMPETITION.fee}
              <IconArrow />
            </button>

            {form.industries.length > 0 && (
              <div className={styles.selectedSummary}>
                <div className={styles.selectedSummaryLabel}>已选行业</div>
                <div className={styles.selectedChipsRow}>
                  {form.industries.map(i => (
                    <span key={i} className={styles.selectedChip}><IconHash />{i}</span>
                  ))}
                </div>
              </div>
            )}
          </form>
        </div>
      </div>

      {showSuccess && lastOrder && (
        <div className={styles.successOverlay} onClick={closeSuccess}>
          <div className={styles.successCard} onClick={e => e.stopPropagation()}>
            <div className={styles.successIcon}><IconCheck /></div>
            <h3 className={styles.successTitle}>报名成功</h3>
            <p className={styles.successDesc}>
              欢迎 <strong>{lastOrder.name}</strong>，组委会将于 24 小时内通过短信发送参赛凭证至 {lastOrder.phone}。
            </p>
            <div className={styles.successOrder}>
              <div className={styles.successOrderRow}>
                <span>订单编号</span><strong>{lastOrder.orderId}</strong>
              </div>
              <div className={styles.successOrderRow}>
                <span>所在地区</span><strong>{lastOrder.location}</strong>
              </div>
              <div className={styles.successOrderRow}>
                <span>所属行业</span><strong>{lastOrder.industries.length} 个</strong>
              </div>
              <div className={styles.successOrderRow}>
                <span>实付金额</span><strong style={{ color: '#1e7a5d' }}>¥{lastOrder.fee}</strong>
              </div>
            </div>
            <button className={styles.successBtn} onClick={closeSuccess}>完成</button>
          </div>
        </div>
      )}
    </div>
  )
}
