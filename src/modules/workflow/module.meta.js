import { defineModule, definePage } from '../../framework/schema.js'

export default defineModule({
  id: 'workflow',
  title: 'Workflow',
  description: 'Visual workflow builder with React Flow',
  order: 3,
  pages: [
    definePage({
      id: 'flow-builder',
      title: 'Flow Builder',
      route: '/workflow/builder',
      entry: './pages/FlowBuilderPage.jsx',
      summary: 'Build workflows with drag-and-drop nodes'
    })
  ],
  widgets: []
})
