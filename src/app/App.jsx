import { Suspense } from 'react'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { AppShell } from '../framework/components/AppShell.jsx'
import { NotFoundPage } from '../framework/components/NotFoundPage.jsx'
import { PageFrame } from '../framework/components/PageFrame.jsx'
import { registry } from '../framework/registry.js'

const pageRoutes = registry.pages.map((page) => {
  if (page.route === '/') {
    return {
      index: true,
      element: <PageFrame page={page} />
    }
  }

  return {
    path: page.route.replace(/^\//, ''),
    element: <PageFrame page={page} />
  }
})

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      ...pageRoutes,
      {
        path: '*',
        element: <NotFoundPage />
      }
    ]
  }
])

export default function App() {
  return (
    <Suspense fallback={<div className="screen-state">正在装载框架入口…</div>}>
      <RouterProvider router={router} />
    </Suspense>
  )
}
