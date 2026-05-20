import { createRouter, createRootRoute, createRoute, Outlet } from '@tanstack/react-router'

const rootRoute = createRootRoute({ component: () => <Outlet /> })

const overviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: () => <div>Overview (Task 34)</div>,
})

const routeTree = rootRoute.addChildren([overviewRoute])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
