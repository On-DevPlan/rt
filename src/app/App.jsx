import { Suspense } from 'react'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import HomePage from './HomePage.jsx'
import { FullscreenPage } from '../framework/components/FullscreenPage.jsx'
import { NotFoundPage } from '../framework/components/NotFoundPage.jsx'
import { registry } from '../framework/registry.js'

const pageRoutes = registry.pages
  .filter((page) => page.route !== '/')
  .map((page) => ({
    path: page.route,
    element: <FullscreenPage page={page} />
  }))

const router = createBrowserRouter([
  {
    path: '/',
    element: <HomePage />
  },
  ...pageRoutes,
  {
    path: '*',
    element: <NotFoundPage />
  }
])

export default function App() {
  return (
    <Suspense fallback={<div className="screen-state">正在装载框架入口…</div>}>
      <RouterProvider router={router} />
    </Suspense>
  )
}
