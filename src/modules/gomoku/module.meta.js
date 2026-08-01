import { defineModule, definePage } from '../../framework/schema.js'

export default defineModule({
  id: 'gomoku',
  title: 'Gomoku Lab',
  description: '五子棋对弈：人机对战（可选先手）、AI 自战、对局中向 AI 求最佳着点。后端无状态实时决策。',
  order: 35,
  color: '#c66bff',
  pages: [
    definePage({
      id: 'gomoku-game',
      title: '五子棋 · AI 对弈',
      route: '/gomoku/game',
      entry: './pages/GomokuPage.jsx',
      summary: '15×15 棋盘，人机/自战两种模式，对局中可让 AI 给出最佳着点。标准连五，无禁手。',
      order: 0,
      tags: ['gomoku', 'game', 'ai', 'heuristic']
    })
  ],
  widgets: []
})
