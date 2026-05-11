import { useState, useMemo, useCallback } from 'react'
import { useDocumentTitle } from '../../../framework/hooks/useDocumentTitle.js'
import styles from './AdminPage.module.css'

const MOCK_DATA = [
  { id: 1, name: '张明远', phone: '13812347621', email: 'zhangmy@mail.com', gender: 'male', status: 'confirmed', time: '05-08 14:32', remark: '需要投影设备' },
  { id: 2, name: '李思琪', phone: '15954343348', email: 'lisq@mail.com', gender: 'female', status: 'confirmed', time: '05-09 09:15', remark: '' },
  { id: 3, name: '王浩然', phone: '18623450092', email: 'wanghr@mail.com', gender: 'male', status: 'pending', time: '05-10 11:47', remark: '素食' },
  { id: 4, name: '赵雨桐', phone: '17767895581', email: 'zhaoyt@mail.com', gender: 'female', status: 'cancelled', time: '05-10 16:03', remark: '' },
  { id: 5, name: '陈子轩', phone: '13698762341', email: 'chenzx@mail.com', gender: 'male', status: 'confirmed', time: '05-11 08:22', remark: '' },
  { id: 6, name: '林诗涵', phone: '15834217890', email: 'linsh@mail.com', gender: 'female', status: 'pending', time: '05-11 10:05', remark: '需要停车证' },
  { id: 7, name: '刘博文', phone: '18256783456', email: 'liubw@mail.com', gender: 'male', status: 'confirmed', time: '05-11 13:48', remark: '' },
  { id: 8, name: '杨若曦', phone: '13543216789', email: 'yangrx@mail.com', gender: 'female', status: 'confirmed', time: '05-11 15:30', remark: '携带笔记本电脑' },
  { id: 9, name: '黄俊杰', phone: '17689012345', email: 'huangjj@mail.com', gender: 'male', status: 'pending', time: '05-11 17:12', remark: '' },
  { id: 10, name: '吴晓彤', phone: '13765432109', email: 'wuxt@mail.com', gender: 'female', status: 'confirmed', time: '05-12 09:45', remark: '' },
  { id: 11, name: '周子墨', phone: '15123456789', email: 'zhouzm@mail.com', gender: 'male', status: 'pending', time: '05-12 11:20', remark: '对花生过敏' },
  { id: 12, name: '郑雅琪', phone: '18909876543', email: 'zhengyq@mail.com', gender: 'female', status: 'cancelled', time: '05-12 14:08', remark: '' },
]

const STATUS_MAP = {
  confirmed: { label: '已确认', className: styles.tagConfirmed },
  pending: { label: '待确认', className: styles.tagPending },
  cancelled: { label: '已取消', className: styles.tagCancelled },
}

const CAPACITY = 30

export default function AdminPage() {
  useDocumentTitle('报名管理后台')

  const [participants, setParticipants] = useState(MOCK_DATA)
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')

  const confirmed = participants.filter(p => p.status === 'confirmed').length
  const pending = participants.filter(p => p.status === 'pending').length
  const cancelled = participants.filter(p => p.status === 'cancelled').length
  const fillRate = Math.round((confirmed / CAPACITY) * 100)

  const filtered = useMemo(() => {
    let list = participants
    if (filter !== 'all') list = list.filter(p => p.status === filter)
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      list = list.filter(p =>
        p.name.toLowerCase().includes(q) ||
        p.phone.includes(q) ||
        p.email.toLowerCase().includes(q)
      )
    }
    return list
  }, [participants, filter, search])

  const handleStatusChange = useCallback((id, newStatus) => {
    setParticipants(prev => prev.map(p => p.id === id ? { ...p, status: newStatus } : p))
  }, [])

  const handleRemove = useCallback((id) => {
    setParticipants(prev => prev.filter(p => p.id !== id))
  }, [])

  return (
    <div className={styles.root}>
      {/* Top Bar */}
      <div className={styles.topBar}>
        <div className={styles.topBarInner}>
          <h1 className={styles.topBarTitle}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            报名管理后台
            <span className={styles.topBarBadge}>Admin</span>
          </h1>
          <div className={styles.topBarMeta}>
            <span>2026 创意设计工作坊</span>
            <span>|</span>
            <span>最后更新: 刚刚</span>
          </div>
        </div>
      </div>

      <div className={styles.container}>
        {/* Dashboard */}
        <div className={styles.dashboard}>
          <div className={styles.dashCard}>
            <div className={styles.dashCardHeader}>
              <span className={styles.dashCardLabel}>总报名</span>
              <div className={`${styles.dashCardIcon} ${styles.dashCardIconBlue}`}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              </div>
            </div>
            <div className={styles.dashCardValue}>{participants.length}</div>
            <div className={styles.dashCardSub}>总容量 {CAPACITY} 人</div>
          </div>
          <div className={styles.dashCard}>
            <div className={styles.dashCardHeader}>
              <span className={styles.dashCardLabel}>已确认</span>
              <div className={`${styles.dashCardIcon} ${styles.dashCardIconGreen}`}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
              </div>
            </div>
            <div className={styles.dashCardValue}>{confirmed}</div>
            <div className={styles.dashCardSub}>签到率 {fillRate}%</div>
          </div>
          <div className={styles.dashCard}>
            <div className={styles.dashCardHeader}>
              <span className={styles.dashCardLabel}>待确认</span>
              <div className={`${styles.dashCardIcon} ${styles.dashCardIconAmber}`}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>
              </div>
            </div>
            <div className={styles.dashCardValue}>{pending}</div>
            <div className={styles.dashCardSub}>需跟进处理</div>
          </div>
          <div className={styles.dashCard}>
            <div className={styles.dashCardHeader}>
              <span className={styles.dashCardLabel}>已取消</span>
              <div className={`${styles.dashCardIcon} ${styles.dashCardIconGray}`}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" /></svg>
              </div>
            </div>
            <div className={styles.dashCardValue}>{cancelled}</div>
            <div className={styles.dashCardSub}>退出率 {participants.length > 0 ? Math.round((cancelled / participants.length) * 100) : 0}%</div>
          </div>
        </div>

        {/* Filter Bar */}
        <div className={styles.filterBar}>
          <div className={styles.filterTabs}>
            {[
              { key: 'all', label: '全部' },
              { key: 'confirmed', label: '已确认' },
              { key: 'pending', label: '待确认' },
              { key: 'cancelled', label: '已取消' },
            ].map(tab => (
              <button
                key={tab.key}
                className={`${styles.filterTab} ${filter === tab.key ? styles.filterTabActive : ''}`}
                onClick={() => setFilter(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className={styles.searchBox}>
            <span className={styles.searchIcon}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </span>
            <input
              className={styles.searchInput}
              type="text"
              placeholder="搜索姓名、手机号、邮箱..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
        </div>

        {/* Table */}
        <div className={styles.tableSection}>
          <div className={styles.tableHeaderBar}>
            <div className={styles.tableHeaderTitle}>
              参与者列表
              <span className={styles.tableHeaderCount}>{filtered.length} 条记录</span>
            </div>
          </div>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>参与者</th>
                <th>手机号</th>
                <th>报名时间</th>
                <th>备注</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(p => {
                const statusInfo = STATUS_MAP[p.status]
                return (
                  <tr key={p.id} className={styles.tableRow}>
                    <td>
                      <div className={styles.participantCell}>
                        <div className={`${styles.avatar} ${p.gender === 'female' ? styles.avatarFemale : styles.avatarMale}`}>
                          {p.name.charAt(0)}
                        </div>
                        <div className={styles.participantInfo}>
                          <span className={styles.participantName}>{p.name}</span>
                          <span className={styles.participantEmail}>{p.email}</span>
                        </div>
                      </div>
                    </td>
                    <td className={styles.phoneCell}>{p.phone.slice(0, 3)}****{p.phone.slice(-4)}</td>
                    <td className={styles.timeCell}>{p.time}</td>
                    <td className={styles.timeCell} style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {p.remark || '—'}
                    </td>
                    <td>
                      <span className={`${styles.tag} ${statusInfo.className}`}>
                        <span className={styles.tagDot} />
                        {statusInfo.label}
                      </span>
                    </td>
                    <td>
                      <div className={styles.actionBtns}>
                        {p.status === 'pending' && (
                          <button className={styles.btnAction} onClick={() => handleStatusChange(p.id, 'confirmed')}>确认</button>
                        )}
                        {p.status !== 'cancelled' && (
                          <button className={`${styles.btnAction} ${styles.btnActionDanger}`} onClick={() => handleStatusChange(p.id, 'cancelled')}>取消</button>
                        )}
                        {p.status === 'cancelled' && (
                          <button className={styles.btnAction} onClick={() => handleStatusChange(p.id, 'pending')}>恢复</button>
                        )}
                        <button className={`${styles.btnAction} ${styles.btnActionDanger}`} onClick={() => handleRemove(p.id)}>删除</button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <div className={styles.tableFooter}>
            <span>显示 {filtered.length} / {participants.length} 条</span>
            <div className={styles.pagination}>
              <button className={styles.pageBtn}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6" /></svg>
              </button>
              <button className={`${styles.pageBtn} ${styles.pageBtnActive}`}>1</button>
              <button className={styles.pageBtn}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6" /></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
