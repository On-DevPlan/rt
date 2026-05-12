import { useState, useMemo, useCallback } from 'react'
import { useDocumentTitle } from '../../../framework/hooks/useDocumentTitle.js'
import styles from './ProTablePage.module.css'

/* ── Mock data ── */
const DATA = [
  { id: 1, name: '张明远', phone: '13812347621', email: 'zhangmy@mail.com', gender: 'male', status: 'confirmed', type: 'vip', time: '2026-05-08 14:32', remark: '需要投影设备' },
  { id: 2, name: '李思琪', phone: '15954343348', email: 'lisq@mail.com', gender: 'female', status: 'confirmed', type: 'normal', time: '2026-05-09 09:15', remark: '' },
  { id: 3, name: '王浩然', phone: '18623450092', email: 'wanghr@mail.com', gender: 'male', status: 'pending', type: 'normal', time: '2026-05-10 11:47', remark: '素食' },
  { id: 4, name: '赵雨桐', phone: '17767895581', email: 'zhaoyt@mail.com', gender: 'female', status: 'cancelled', type: 'vip', time: '2026-05-10 16:03', remark: '' },
  { id: 5, name: '陈子轩', phone: '13698762341', email: 'chenzx@mail.com', gender: 'male', status: 'confirmed', type: 'normal', time: '2026-05-11 08:22', remark: '' },
  { id: 6, name: '林诗涵', phone: '15834217890', email: 'linsh@mail.com', gender: 'female', status: 'pending', type: 'vip', time: '2026-05-11 10:05', remark: '需要停车证' },
  { id: 7, name: '刘博文', phone: '18256783456', email: 'liubw@mail.com', gender: 'male', status: 'confirmed', type: 'normal', time: '2026-05-11 13:48', remark: '' },
  { id: 8, name: '杨若曦', phone: '13543216789', email: 'yangrx@mail.com', gender: 'female', status: 'confirmed', type: 'vip', time: '2026-05-11 15:30', remark: '携带笔记本电脑' },
  { id: 9, name: '黄俊杰', phone: '17689012345', email: 'huangjj@mail.com', gender: 'male', status: 'pending', type: 'normal', time: '2026-05-11 17:12', remark: '' },
  { id: 10, name: '吴晓彤', phone: '13765432109', email: 'wuxt@mail.com', gender: 'female', status: 'confirmed', type: 'normal', time: '2026-05-12 09:45', remark: '' },
  { id: 11, name: '周子墨', phone: '15123456789', email: 'zhouzm@mail.com', gender: 'male', status: 'pending', type: 'vip', time: '2026-05-12 11:20', remark: '对花生过敏' },
  { id: 12, name: '郑雅琪', phone: '18909876543', email: 'zhengyq@mail.com', gender: 'female', status: 'cancelled', type: 'normal', time: '2026-05-12 14:08', remark: '' },
  { id: 13, name: '孙一鸣', phone: '13800138000', email: 'sunym@mail.com', gender: 'male', status: 'confirmed', type: 'vip', time: '2026-05-12 16:30', remark: '' },
  { id: 14, name: '马晨曦', phone: '15012349876', email: 'macx@mail.com', gender: 'female', status: 'pending', type: 'normal', time: '2026-05-13 08:15', remark: '' },
  { id: 15, name: '何志远', phone: '18698765432', email: 'hezy@mail.com', gender: 'male', status: 'confirmed', type: 'normal', time: '2026-05-13 10:42', remark: '需要无障碍通道' },
  { id: 16, name: '罗心怡', phone: '17756781234', email: 'luoxy@mail.com', gender: 'female', status: 'confirmed', type: 'vip', time: '2026-05-13 14:18', remark: '' },
  { id: 17, name: '许天宇', phone: '13643215678', email: 'xuty@mail.com', gender: 'male', status: 'cancelled', type: 'normal', time: '2026-05-13 16:55', remark: '' },
  { id: 18, name: '谢芷若', phone: '15887654321', email: 'xiezr@mail.com', gender: 'female', status: 'confirmed', type: 'normal', time: '2026-05-14 09:30', remark: '' },
]

const STATUS_MAP = {
  confirmed: { label: '已确认', cls: styles.tagConfirmed },
  pending: { label: '待确认', cls: styles.tagPending },
  cancelled: { label: '已取消', cls: styles.tagCancelled },
}

const TYPE_MAP = {
  vip: { label: 'VIP', cls: styles.tagVip },
  normal: { label: '普通', cls: styles.tagNormal },
}

const PAGE_SIZES = [5, 10, 20]

const DENSITY_ORDER = ['default', 'compact', 'loose']
const DENSITY_ICON = {
  default: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  ),
  compact: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <line x1="3" y1="8" x2="21" y2="8" /><line x1="3" y1="16" x2="21" y2="16" />
    </svg>
  ),
  loose: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <line x1="3" y1="5" x2="21" y2="5" /><line x1="3" y1="10" x2="21" y2="10" /><line x1="3" y1="15" x2="21" y2="15" /><line x1="3" y1="20" x2="21" y2="20" />
    </svg>
  ),
}

export default function ProTablePage() {
  useDocumentTitle('ProTable 案例')

  /* ── Search state ── */
  const [searchForm, setSearchForm] = useState({ name: '', status: '', type: '', dateRange: '' })
  const [appliedSearch, setAppliedSearch] = useState({ name: '', status: '', type: '', dateRange: '' })

  /* ── Table state ── */
  const [data, setData] = useState(DATA)
  const [selectedKeys, setSelectedKeys] = useState(new Set())
  const [sortField, setSortField] = useState(null)
  const [sortDir, setSortDir] = useState(null)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(5)
  const [density, setDensity] = useState('default')
  const [loading, setLoading] = useState(false)

  /* ── Filter + sort ── */
  const filtered = useMemo(() => {
    let list = data
    const s = appliedSearch
    if (s.name) {
      const q = s.name.toLowerCase()
      list = list.filter(r => r.name.toLowerCase().includes(q) || r.email.toLowerCase().includes(q) || r.phone.includes(q))
    }
    if (s.status) list = list.filter(r => r.status === s.status)
    if (s.type) list = list.filter(r => r.type === s.type)
    if (sortField) {
      list = [...list].sort((a, b) => {
        const va = a[sortField]
        const vb = b[sortField]
        if (va < vb) return sortDir === 'asc' ? -1 : 1
        if (va > vb) return sortDir === 'asc' ? 1 : -1
        return 0
      })
    }
    return list
  }, [data, appliedSearch, sortField, sortDir])

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const currentPage = Math.min(page, totalPages)
  const paged = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize)

  /* ── Handlers ── */
  const handleSearch = useCallback(() => {
    setLoading(true)
    setSelectedKeys(new Set())
    setPage(1)
    setTimeout(() => {
      setAppliedSearch({ ...searchForm })
      setLoading(false)
    }, 400)
  }, [searchForm])

  const handleReset = useCallback(() => {
    setSearchForm({ name: '', status: '', type: '', dateRange: '' })
    setAppliedSearch({ name: '', status: '', type: '', dateRange: '' })
    setSelectedKeys(new Set())
    setPage(1)
  }, [])

  const toggleSort = useCallback((field) => {
    setPage(1)
    if (sortField === field) {
      if (sortDir === 'asc') setSortDir('desc')
      else if (sortDir === 'desc') { setSortField(null); setSortDir(null) }
    } else {
      setSortField(field)
      setSortDir('asc')
    }
  }, [sortField, sortDir])

  const toggleSelect = useCallback((id) => {
    setSelectedKeys(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const toggleSelectAll = useCallback(() => {
    const pageIds = paged.map(r => r.id)
    const allSelected = pageIds.every(id => selectedKeys.has(id))
    if (allSelected) {
      setSelectedKeys(prev => {
        const next = new Set(prev)
        pageIds.forEach(id => next.delete(id))
        return next
      })
    } else {
      setSelectedKeys(prev => new Set([...prev, ...pageIds]))
    }
  }, [paged, selectedKeys])

  const handleBatchDelete = useCallback(() => {
    setData(prev => prev.filter(r => !selectedKeys.has(r.id)))
    setSelectedKeys(new Set())
  }, [selectedKeys])

  const handleBatchConfirm = useCallback(() => {
    setData(prev => prev.map(r => selectedKeys.has(r.id) ? { ...r, status: 'confirmed' } : r))
    setSelectedKeys(new Set())
  }, [selectedKeys])

  const handleDelete = useCallback((id) => {
    setData(prev => prev.filter(r => r.id !== id))
    setSelectedKeys(prev => { const n = new Set(prev); n.delete(id); return n })
  }, [])

  const cycleDensity = useCallback(() => {
    setDensity(prev => {
      const idx = DENSITY_ORDER.indexOf(prev)
      return DENSITY_ORDER[(idx + 1) % DENSITY_ORDER.length]
    })
  }, [])

  /* ── Derived ── */
  const pageIds = paged.map(r => r.id)
  const allSelected = pageIds.length > 0 && pageIds.every(id => selectedKeys.has(id))
  const someSelected = pageIds.some(id => selectedKeys.has(id)) && !allSelected

  const densityClass = density === 'compact' ? styles.densityCompact : density === 'loose' ? styles.densityLoose : ''

  return (
    <div className={styles.root}>
      <div className={styles.topBar}>
        <div className={styles.topBarInner}>
          <h1 className={styles.topBarTitle}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <line x1="3" y1="9" x2="21" y2="9" />
              <line x1="9" y1="21" x2="9" y2="9" />
            </svg>
            ProTable 案例
          </h1>
          <span className={styles.topBarDesc}>高级表格组件 — 搜索 / 筛选 / 排序 / 批量操作 / 分页</span>
        </div>
      </div>

      <div className={styles.container}>
        {/* Search */}
        <div className={styles.searchCard}>
          <div className={styles.searchHeader}>
            <div className={styles.searchTitle}>
              <span className={styles.searchTitleIcon}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
              </span>
              查询条件
            </div>
          </div>
          <div className={styles.searchFields}>
            <div className={styles.searchField}>
              <label className={styles.searchLabel}>姓名 / 手机 / 邮箱</label>
              <input className={styles.searchInput} placeholder="关键词搜索" value={searchForm.name} onChange={e => setSearchForm(p => ({ ...p, name: e.target.value }))} />
            </div>
            <div className={styles.searchField}>
              <label className={styles.searchLabel}>状态</label>
              <select className={styles.searchSelect} value={searchForm.status} onChange={e => setSearchForm(p => ({ ...p, status: e.target.value }))}>
                <option value="">全部状态</option>
                <option value="confirmed">已确认</option>
                <option value="pending">待确认</option>
                <option value="cancelled">已取消</option>
              </select>
            </div>
            <div className={styles.searchField}>
              <label className={styles.searchLabel}>类型</label>
              <select className={styles.searchSelect} value={searchForm.type} onChange={e => setSearchForm(p => ({ ...p, type: e.target.value }))}>
                <option value="">全部类型</option>
                <option value="vip">VIP</option>
                <option value="normal">普通</option>
              </select>
            </div>
            <div className={styles.searchField}>
              <label className={styles.searchLabel}>报名时间</label>
              <input className={styles.searchInput} type="date" value={searchForm.dateRange} onChange={e => setSearchForm(p => ({ ...p, dateRange: e.target.value }))} />
            </div>
          </div>
          <div className={styles.searchActions}>
            <button className={styles.btnSearch} onClick={handleSearch}>查询</button>
            <button className={styles.btnReset} onClick={handleReset}>重置</button>
          </div>
        </div>

        {/* Batch Actions */}
        {selectedKeys.size > 0 && (
          <div className={styles.alertBar}>
            <span className={styles.alertInfo}>已选择 {selectedKeys.size} 项</span>
            <div className={styles.alertActions}>
              <button className={`${styles.btnAlert} ${styles.btnAlertPrimary}`} onClick={handleBatchConfirm}>批量确认</button>
              <button className={`${styles.btnAlert} ${styles.btnAlertDanger}`} onClick={handleBatchDelete}>批量删除</button>
              <button className={`${styles.btnAlert} ${styles.btnAlertGhost}`} onClick={() => setSelectedKeys(new Set())}>取消选择</button>
            </div>
          </div>
        )}

        {/* Table */}
        <div className={`${styles.tableCard} ${densityClass}`}>
          {/* Loading bar */}
          {loading && <div className={styles.loadingBar}><div className={styles.loadingBarInner} /></div>}

          {/* Toolbar */}
          <div className={styles.toolbar}>
            <div className={styles.toolbarLeft}>
              <span className={styles.toolbarTitle}>参与者列表</span>
              <span className={styles.toolbarCount}>{filtered.length} 条记录</span>
            </div>
            <div className={styles.toolbarRight}>
              <button className={styles.toolBtn} title="刷新" onClick={() => { setLoading(true); setTimeout(() => setLoading(false), 500) }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                </svg>
              </button>
              <button className={styles.toolBtn} title="密度" onClick={cycleDensity}>
                {DENSITY_ICON[density]}
              </button>
              <div className={styles.toolDivider} />
              <button className={styles.toolBtn} title="全屏" onClick={() => {
                const el = document.querySelector(`.${styles.tableCard}`)
                if (el) el.requestFullscreen?.()
              }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="15 3 21 3 21 9" /><polyline points="9 21 3 21 3 15" /><line x1="21" y1="3" x2="14" y2="10" /><line x1="3" y1="21" x2="10" y2="14" />
                </svg>
              </button>
            </div>
          </div>

          {/* Table */}
          <div className={styles.tableWrap}>
            {paged.length === 0 && !loading ? (
              <div className={styles.emptyState}>
                <div className={styles.emptyIcon}>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
                  </svg>
                </div>
                <p className={styles.emptyText}>没有找到匹配的数据</p>
              </div>
            ) : (
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th style={{ width: 40 }}>
                      <input
                        type="checkbox"
                        className={`${styles.ck} ${someSelected ? styles.ckIndeterminate : ''}`}
                        checked={allSelected}
                        onChange={toggleSelectAll}
                        ref={el => { if (el) el.indeterminate = someSelected }}
                      />
                    </th>
                    <th className={styles.thSortable} onClick={() => toggleSort('name')}>
                      <div className={styles.thContent}>
                        参与者
                        <span className={styles.sortIcon}>
                          <span className={`${styles.sortArrow} ${styles.sortArrowAsc} ${sortField === 'name' && sortDir === 'asc' ? styles.sortArrowAscActive : ''}`} />
                          <span className={`${styles.sortArrow} ${styles.sortArrowDesc} ${sortField === 'name' && sortDir === 'desc' ? styles.sortArrowDescActive : ''}`} />
                        </span>
                      </div>
                    </th>
                    <th>手机号</th>
                    <th className={styles.thSortable} onClick={() => toggleSort('type')}>
                      <div className={styles.thContent}>
                        类型
                        <span className={styles.sortIcon}>
                          <span className={`${styles.sortArrow} ${styles.sortArrowAsc} ${sortField === 'type' && sortDir === 'asc' ? styles.sortArrowAscActive : ''}`} />
                          <span className={`${styles.sortArrow} ${styles.sortArrowDesc} ${sortField === 'type' && sortDir === 'desc' ? styles.sortArrowDescActive : ''}`} />
                        </span>
                      </div>
                    </th>
                    <th className={styles.thSortable} onClick={() => toggleSort('status')}>
                      <div className={styles.thContent}>
                        状态
                        <span className={styles.sortIcon}>
                          <span className={`${styles.sortArrow} ${styles.sortArrowAsc} ${sortField === 'status' && sortDir === 'asc' ? styles.sortArrowAscActive : ''}`} />
                          <span className={`${styles.sortArrow} ${styles.sortArrowDesc} ${sortField === 'status' && sortDir === 'desc' ? styles.sortArrowDescActive : ''}`} />
                        </span>
                      </div>
                    </th>
                    <th className={styles.thSortable} onClick={() => toggleSort('time')}>
                      <div className={styles.thContent}>
                        报名时间
                        <span className={styles.sortIcon}>
                          <span className={`${styles.sortArrow} ${styles.sortArrowAsc} ${sortField === 'time' && sortDir === 'asc' ? styles.sortArrowAscActive : ''}`} />
                          <span className={`${styles.sortArrow} ${styles.sortArrowDesc} ${sortField === 'time' && sortDir === 'desc' ? styles.sortArrowDescActive : ''}`} />
                        </span>
                      </div>
                    </th>
                    <th style={{ width: 130 }}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {paged.map(row => {
                    const s = STATUS_MAP[row.status]
                    const t = TYPE_MAP[row.type]
                    const isSelected = selectedKeys.has(row.id)
                    return (
                      <tr key={row.id} className={`${styles.tableRow} ${isSelected ? styles.tableRowSelected : ''}`}>
                        <td>
                          <input type="checkbox" className={styles.ck} checked={isSelected} onChange={() => toggleSelect(row.id)} />
                        </td>
                        <td>
                          <div className={styles.cellUser}>
                            <div className={`${styles.avatar} ${row.gender === 'female' ? styles.avatarFemale : styles.avatarMale}`}>
                              {row.name.charAt(0)}
                            </div>
                            <div>
                              <div className={styles.userName}>{row.name}</div>
                              <div className={styles.userEmail}>{row.email}</div>
                            </div>
                          </div>
                        </td>
                        <td className={styles.phoneCell}>{row.phone.slice(0, 3)}****{row.phone.slice(-4)}</td>
                        <td>
                          <span className={`${styles.tag} ${t.cls}`}>
                            <span className={styles.tagDot} />
                            {t.label}
                          </span>
                        </td>
                        <td>
                          <span className={`${styles.tag} ${s.cls}`}>
                            <span className={styles.tagDot} />
                            {s.label}
                          </span>
                        </td>
                        <td className={styles.timeCell}>{row.time}</td>
                        <td>
                          <div className={styles.cellActions}>
                            <button className={`${styles.actBtn} ${styles.actBtnView}`}>查看</button>
                            <button className={`${styles.actBtn} ${styles.actBtnEdit}`}>编辑</button>
                            <button className={`${styles.actBtn} ${styles.actBtnDel}`} onClick={() => handleDelete(row.id)}>删除</button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>

          {/* Footer */}
          {paged.length > 0 && (
            <div className={styles.tableFooter}>
              <div className={styles.footerInfo}>
                共 {filtered.length} 条，第 {currentPage}/{totalPages} 页
                <select className={styles.pageSizeSelect} value={pageSize} onChange={e => { setPageSize(Number(e.target.value)); setPage(1) }}>
                  {PAGE_SIZES.map(s => <option key={s} value={s}>{s} 条/页</option>)}
                </select>
              </div>
              <div className={styles.pagination}>
                <button className={`${styles.pageBtn} ${currentPage <= 1 ? styles.pageBtnDisabled : ''}`} disabled={currentPage <= 1} onClick={() => setPage(1)}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="11 17 6 12 11 7" /><polyline points="18 17 13 12 18 7" /></svg>
                </button>
                <button className={`${styles.pageBtn} ${currentPage <= 1 ? styles.pageBtnDisabled : ''}`} disabled={currentPage <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="15 18 9 12 15 6" /></svg>
                </button>
                {Array.from({ length: totalPages }, (_, i) => i + 1)
                  .filter(p => p === 1 || p === totalPages || Math.abs(p - currentPage) <= 1)
                  .reduce((acc, p, i, arr) => {
                    if (i > 0 && p - arr[i - 1] > 1) acc.push('...')
                    acc.push(p)
                    return acc
                  }, [])
                  .map((p, i) =>
                    p === '...'
                      ? <span key={`e${i}`} style={{ color: 'var(--c-text-tertiary)', fontSize: 12, padding: '0 4px' }}>...</span>
                      : <button key={p} className={`${styles.pageBtn} ${p === currentPage ? styles.pageBtnActive : ''}`} onClick={() => setPage(p)}>{p}</button>
                  )
                }
                <button className={`${styles.pageBtn} ${currentPage >= totalPages ? styles.pageBtnDisabled : ''}`} disabled={currentPage >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="9 18 15 12 9 6" /></svg>
                </button>
                <button className={`${styles.pageBtn} ${currentPage >= totalPages ? styles.pageBtnDisabled : ''}`} disabled={currentPage >= totalPages} onClick={() => setPage(totalPages)}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="13 17 18 12 13 7" /><polyline points="6 17 11 12 6 7" /></svg>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
