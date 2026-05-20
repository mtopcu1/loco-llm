import { createRootRoute, createRoute, createRouter } from '@tanstack/react-router'
import { OverviewPage } from '@/features/overview/OverviewPage'
import { RuntimesPage } from '@/features/runtimes/RuntimesPage'
import { RuntimeDetailPage } from '@/features/runtimes/RuntimeDetailPage'
import { ModelsPage } from '@/features/models/ModelsPage'
import { ModelDetailPage } from '@/features/models/ModelDetailPage'
import { ConfigsPage } from '@/features/configs/ConfigsPage'
import { ConfigDetailPage } from '@/features/configs/ConfigDetailPage'
import { NewConfigPage } from '@/features/configs/NewConfigPage'
import { InstancePage } from '@/features/instance/InstancePage'
import { DoctorPage } from '@/features/doctor/DoctorPage'
import { DiskPage } from '@/features/disk/DiskPage'
import { HistoryPage } from '@/features/history/HistoryPage'
import { SettingsPage } from '@/features/settings/SettingsPage'

const rootRoute = createRootRoute()

const overviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: OverviewPage,
})

const runtimesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/runtimes',
  component: RuntimesPage,
})

const runtimeDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/runtimes/$id',
  component: RuntimeDetailPage,
})

const modelsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/models',
  component: ModelsPage,
})

const modelDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/models/$id',
  component: ModelDetailPage,
})

const configsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/configs',
  component: ConfigsPage,
})

const configDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/configs/$id',
  component: ConfigDetailPage,
})

const newConfigRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/configs/new',
  component: NewConfigPage,
})

const instanceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/instance',
  component: InstancePage,
})

const doctorRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/doctor',
  component: DoctorPage,
})

const diskRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/disk',
  component: DiskPage,
})

const historyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/history',
  component: HistoryPage,
})

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings',
  component: SettingsPage,
})

export const routeTree = rootRoute.addChildren([
  overviewRoute,
  runtimesRoute,
  runtimeDetailRoute,
  modelsRoute,
  modelDetailRoute,
  configsRoute,
  newConfigRoute,
  configDetailRoute,
  instanceRoute,
  doctorRoute,
  diskRoute,
  historyRoute,
  settingsRoute,
])

export type TestRouter = ReturnType<typeof createRouter<typeof routeTree>>

declare module '@tanstack/react-router' {
  interface Register {
    router: TestRouter
  }
}
