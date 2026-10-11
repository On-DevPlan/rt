import * as api from '../services/proxyApi.js'

const BASE = 'http://127.0.0.1:8080/api/proxy'

export const proxyEndpoints = [
  {
    id: 'status',
    title: '代理状态',
    description:
      '全景：订阅是否已填、开关状态、是否真正生效（effective = enabled 且 mihomo 存活且代理 client 就绪）、mihomo 版本/节点数、出口 IP 对比（direct = 服务器直连出口，proxied = 白名单请求经 mihomo 的出口）。',
    method: 'GET',
    path: '/api/proxy/status',
    inputs: [{ name: 'check_ip', label: '探测出口 IP（直连 vs 代理对比）', type: 'bool', default: true }],
    buildCurl: (v) => `curl "${BASE}/status?check_ip=${v.check_ip !== false}"`,
    submit: (v) => api.status({ check_ip: v.check_ip !== false })
  },
  {
    id: 'set-subscription',
    title: '填写订阅 URL',
    description:
      '拉取订阅 → 校验（自动识别"原始节点分享链接列表"并拒绝）→ 与基础模板安全合并（容器端口 / 控制面 / tun / dns 等键我方全胜，订阅只带节点/分组/规则）→ 落盘并热重载 mihomo。不改变启用开关。首次拉取走服务器直连（此时还没有代理可用）。',
    method: 'PUT',
    path: '/api/proxy/subscription',
    inputs: [
      {
        name: 'url',
        label: 'Clash 订阅 URL',
        type: 'text',
        sensitive: true,
        placeholder: 'https://panel.example.com/sub?token=...'
      }
    ],
    buildCurl: (v) =>
      `curl -X PUT "${BASE}/subscription" -H "Content-Type: application/json" -d '${JSON.stringify({ url: v.url })}'`,
    submit: (v) => api.setSubscription(v.url)
  },
  {
    id: 'toggle',
    title: '启用 / 停用代理',
    description:
      'enabled=true 需已填订阅且 mihomo 存活。只影响白名单里的模块，其余模块始终直连。',
    method: 'POST',
    path: '/api/proxy/toggle',
    inputs: [{ name: 'enabled', label: 'enabled（true = 白名单模块走代理）', type: 'bool', default: false }],
    buildCurl: (v) =>
      `curl -X POST "${BASE}/toggle" -H "Content-Type: application/json" -d '{"enabled":${!!v.enabled}}'`,
    submit: (v) => api.toggle(!!v.enabled)
  },
  {
    id: 'allowlist',
    title: '模块白名单',
    description:
      '允许走代理的模块名（即时生效，无需重启）。可选值：skill_seekers / anime_season / mediacrawler / bilibili_crawler / bilibili_history / bilibili_tools / sicau_timetable。空列表 = 全部直连。',
    method: 'PUT',
    path: '/api/proxy/allowlist',
    inputs: [
      {
        name: 'modules',
        label: '模块名（每行一个）',
        type: 'list',
        default: 'skill_seekers',
        placeholder: 'skill_seekers\nanime_season'
      }
    ],
    buildCurl: (v) =>
      `curl -X PUT "${BASE}/allowlist" -H "Content-Type: application/json" -d '${JSON.stringify({ modules: v.modules || [] })}'`,
    submit: (v) => api.setAllowlist(v.modules || [])
  },
  {
    id: 'refresh',
    title: '刷新订阅',
    description: '用已存的订阅 URL 重新拉取并热重载（订阅更新或 mihomo 恢复后重试）。',
    method: 'POST',
    path: '/api/proxy/refresh',
    inputs: [],
    buildCurl: () => `curl -X POST "${BASE}/refresh"`,
    submit: () => api.refresh()
  },
  {
    id: 'clear-subscription',
    title: '清除订阅（重置）',
    description: '关闭代理、清空已存订阅 URL、把 mihomo 配置复位为空跑 stub（MATCH,DIRECT）。',
    method: 'DELETE',
    path: '/api/proxy/subscription',
    inputs: [],
    buildCurl: () => `curl -X DELETE "${BASE}/subscription"`,
    submit: () => api.clearSubscription()
  }
]
