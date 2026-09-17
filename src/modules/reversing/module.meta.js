import { defineModule, definePage } from '../../framework/schema.js'

export default defineModule({
  id: 'reversing',
  title: 'Reversing',
  description: '埋在前端源码里的一套逆向题。打通九关拿群号。',
  order: 40,
  color: '#a65131',
  pages: [
    definePage({
      id: 'reversing-challenge',
      title: 'F12 逆向挑战',
      route: '/reversing',
      entry: './pages/ReversingPage.jsx',
      summary:
        '这套页面看得见的部分只是说明，题目全在没有被压缩的源码里。九关覆盖断点调试、函数重写、反调试对抗、抓包签名、响应解密、Node 补环境与工作量证明。',
      order: 10,
      tags: ['reversing', 'devtools', 'puzzle'],
      showcase: true,
      fullscreen: false
    })
  ]
})
