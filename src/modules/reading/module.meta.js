import { defineModule, definePage } from '../../framework/schema.js'

export default defineModule({
  id: 'reading',
  title: 'Reading Studio',
  description: '句子级悬停阅读实验页，用于验证逐句聚焦和延迟触发朗读。',
  order: 20,
  color: '#235c86',
  pages: [
    definePage({
      id: 'story-reader',
      title: 'Sentence Reader',
      route: '/reading/story',
      entry: './pages/SentenceReaderPage.jsx',
      summary: '英语短文被拆成卡片；悬停某一句 3 秒不移动，就触发一次模拟朗读提示。',
      order: 0,
      tags: ['reading', 'sentence', 'hover', 'progress']
    })
  ],
  widgets: []
})
