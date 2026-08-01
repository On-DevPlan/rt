import { defineModule, definePage } from '../../framework/schema.js'

export default defineModule({
  id: 'tetris',
  title: 'Tetris Lab',
  description: '俄罗斯方块，键盘操作；后端 Pierre Dellacherie 算法实时给出最佳落法，支持一键执行。',
  order: 30,
  color: '#5ad1ff',
  pages: [
    definePage({
      id: 'tetris-game',
      title: 'Tetris · AI 提示',
      route: '/tetris/game',
      entry: './pages/TetrisGamePage.jsx',
      summary: '10×20 棋盘，A/D/W/S/Space 控制，蓝色方框为后端 AI 推荐的最终落点，按 G 一键执行。',
      order: 0,
      tags: ['tetris', 'game', 'ai', 'dai', 'heuristic']
    })
  ],
  widgets: []
})
