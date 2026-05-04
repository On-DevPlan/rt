import { defineModule, definePage } from '../../framework/schema.js'

export default defineModule({
  id: 'showcase',
  title: 'Showcase',
  description: 'Immersive parallax scrolling experience with 3D visual effects',
  order: 5,
  color: '#6366f1',
  pages: [
    definePage({
      id: 'parallax-showcase',
      title: 'Parallax Showcase',
      route: '/showcase/parallax',
      entry: './pages/ParallaxShowcasePage.jsx',
      summary: 'An immersive visual experience with parallax scrolling and 3D effects',
      order: 0,
      tags: ['parallax', '3d', 'visual'],
      widgets: [],
      showcase: true,
      fullscreen: true
    })
  ],
  widgets: []
})
