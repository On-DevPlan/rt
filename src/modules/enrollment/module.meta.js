import { defineModule, definePage } from '../../framework/schema.js'

export default defineModule({
  id: 'enrollment',
  title: 'Enrollment',
  description: 'Event registration and participant management system',
  order: 6,
  color: '#1e7a5d',
  pages: [
    definePage({
      id: 'enrollment-main',
      title: '报名管理',
      route: '/enrollment/main',
      entry: './pages/EnrollmentPage.jsx',
      summary: 'Event registration form with participant management',
      order: 0,
      tags: ['enrollment', 'form', 'management'],
      widgets: [],
      showcase: true,
      fullscreen: true
    }),
    definePage({
      id: 'enrollment-admin',
      title: '报名后台',
      route: '/enrollment/admin',
      entry: './pages/AdminPage.jsx',
      summary: 'Admin dashboard for managing enrollment participants',
      order: 1,
      tags: ['admin', 'dashboard', 'management'],
      showcase: true,
      fullscreen: true
    }),
    definePage({
      id: 'enrollment-protable',
      title: 'ProTable 案例',
      route: '/enrollment/protable',
      entry: './pages/ProTablePage.jsx',
      summary: 'Advanced table with search, sort, selection, density, pagination',
      order: 2,
      tags: ['protable', 'table', 'advanced'],
      showcase: true,
      fullscreen: true
    }),
    definePage({
      id: 'enrollment-competition',
      title: '赛事报名',
      route: '/enrollment/competition',
      entry: './pages/CompetitionPage.jsx',
      summary: 'Competition registration with rules, prize, news timeline, address and cascading region select',
      order: 3,
      tags: ['competition', 'registration', 'cascader'],
      showcase: true,
      fullscreen: true
    })
  ],
  widgets: []
})
