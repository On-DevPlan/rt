import { defineModule, definePage } from '../../framework/schema.js'

export default defineModule({
  id: 'algorithm',
  title: 'Algorithm Lab',
  description: '可视化算法逐步构建过程，左侧代码+状态变化，右侧步骤编号与解题思路，TOML 驱动的动画播放器。',
  order: 15,
  color: '#00f0ff',
  pages: [
    definePage({
      id: 'algo-visualizer',
      title: '算法可视化',
      route: '/algo/visualizer',
      entry: './pages/AlgoVisualizerPage.jsx',
      summary: 'LeetCode 算法从 0 到 1 的逐步构建动画，左屏算法过程，右屏思路解析，渐入效果播放。',
      order: 0,
      tags: ['algorithm', 'visualization', 'leetcode', 'animation'],
      fullscreen: true
    })
  ],
  widgets: []
})
