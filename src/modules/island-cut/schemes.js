/**
 * Island Cut 模块的方案 tab 配置。
 *   新增方案只需在这里追加一项 + 在 pages/ 下放一个 Panel 组件。
 *
 * 注意：*Panel.jsx 后缀不在 module.meta.js 的 pages glob（*Page.jsx）中，
 * 不会被错误注册为路由入口。
 */

export const ISLAND_CUT_TABS = [
  {
    id: 'image-cut',
    label: '图片切割',
  },
  {
    id: 'video-gif',
    label: '视频 → GIF',
  },
  {
    id: 'video-webp',
    label: '视频 → WebP',
  },
  {
    id: 'video-apng',
    label: '视频 → APNG',
    badge: '未来',
  },
]