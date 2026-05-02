import { defineModule, definePage, defineWidget } from '../../framework/schema.js'

export default defineModule({
  id: 'lab',
  title: 'Lab Sandbox',
  description: '专门放实验性页面和基础能力验证。',
  order: 10,
  color: '#a65131',
  pages: [
    definePage({
      id: 'sandbox',
      title: '模块沙箱',
      route: '/lab/sandbox',
      entry: './pages/SandboxPage.jsx',
      summary: '说明如何把一个新业务域接到这个框架里，同时保留隔离性和懒加载。',
      order: 0,
      tags: ['sandbox', 'module', 'performance'],
      widgets: ['prefetch-strategy']
    })
  ],
  widgets: [
    defineWidget({
      id: 'prefetch-strategy',
      title: 'Prefetch Strategy',
      entry: './widgets/PrefetchStrategyWidget.jsx',
      summary: '说明 hover 预加载和 metadata eager import 的组合策略。',
      order: 0,
      tags: ['prefetch', 'lazy']
    })
  ]
})
