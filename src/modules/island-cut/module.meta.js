import { defineModule, definePage } from '../../framework/schema.js'

export default defineModule({
  id: 'island-cut',
  title: 'Island Cut',
  description: '上传图片按连通域岛屿切割，导出带透明通道的像素块 PNG，一键打包 ZIP。透明底/白底源图均支持。',
  order: 40,
  color: '#2f9e8f',
  pages: [
    definePage({
      id: 'island-cut-studio',
      title: '岛屿切割 · 透明像素块',
      route: '/island-cut/studio',
      entry: './pages/IslandCutPage.jsx',
      summary: '上传透明底或白底图，按连通域岛屿切成独立透明 PNG 切片，可调阈值/闭运算/最小面积等参数，支持在线预览与 ZIP 快速下载。',
      order: 0,
      tags: ['image', 'alpha', 'connected-components', 'scipy', 'spritesheet']
    })
  ],
  widgets: []
})
