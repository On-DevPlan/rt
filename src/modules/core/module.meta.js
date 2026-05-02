import { defineModule, definePage, defineWidget } from '../../framework/schema.js'

export default defineModule({
  id: 'core',
  title: 'Core Registry',
  description: '核心外壳、自动注册和总览入口。',
  order: 0,
  color: '#1e7a5d',
  pages: [
    definePage({
      id: 'registry-explorer',
      title: '注册表总览',
      route: '/registry',
      entry: './pages/RegistryExplorerPage.jsx',
      summary: '查看所有模块、页面和 widgets 的自动发现结果，并验证元数据是否集中。',
      order: 10,
      tags: ['metadata', 'inspection', 'search'],
      widgets: ['isolation-contract'],
      showcase: false,
      internal: true
    })
  ],
  widgets: [
    defineWidget({
      id: 'registry-stats',
      title: 'Registry Stats',
      entry: './widgets/RegistryStatsWidget.jsx',
      summary: '显示当前 registry 的模块、页面、组件统计。',
      order: 0,
      tags: ['stats', 'registry']
    }),
    defineWidget({
      id: 'route-map',
      title: 'Route Map',
      entry: './widgets/RouteMapWidget.jsx',
      summary: '快速确认自动注册后的路由树。',
      order: 10,
      tags: ['routes']
    }),
    defineWidget({
      id: 'isolation-contract',
      title: 'Isolation Contract',
      entry: './widgets/IsolationContractWidget.jsx',
      summary: '说明模块自包含的约定和边界。',
      order: 20,
      tags: ['isolation', 'contracts']
    })
  ]
})
