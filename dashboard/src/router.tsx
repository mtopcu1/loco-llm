import { createRouter, createRootRoute, createRoute, Outlet } from '@tanstack/react-router'
import { Layout } from '@/components/Layout'

function Placeholder({ name }: { name: string }) {
  return <div className="text-zinc-600">{name}</div>
}

const rootRoute = createRootRoute({
  component: () => (
    <Layout>
      <Outlet />
    </Layout>
  ),
})

const overviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: () => <Placeholder name="Overview (Task 32)" />,
})

const runtimesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/runtimes',
  component: () => <Placeholder name="Runtimes (Task 33)" />,
})

const runtimeDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/runtimes/$id',
  component: () => <Placeholder name="Runtime Detail (Task 33)" />,
})

const modelsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/models',
  component: () => <Placeholder name="Models (Task 34)" />,
})

const modelDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/models/$id',
  component: () => <Placeholder name="Model Detail (Task 34)" />,
})

const configsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/configs',
  component: () => <Placeholder name="Configs (Task 35)" />,
})

const configDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/configs/$id',
  component: () => <Placeholder name="Config Detail (Task 35)" />,
})

const instanceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/instance',
  component: () => <Placeholder name="Instance (Task 36)" />,
})

const doctorRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/doctor',
  component: () => <Placeholder name="Doctor (Task 37)" />,
})

const diskRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/disk',
  component: () => <Placeholder name="Disk (Task 38)" />,
})

const historyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/history',
  component: () => <Placeholder name="History (Task 39)" />,
})

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings',
  component: () => <Placeholder name="Settings (Task 40)" />,
})

const routeTree = rootRoute.addChildren([
  overviewRoute,
  runtimesRoute,
  runtimeDetailRoute,
  modelsRoute,
  modelDetailRoute,
  configsRoute,
  configDetailRoute,
  instanceRoute,
  doctorRoute,
  diskRoute,
  historyRoute,
  settingsRoute,
])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
