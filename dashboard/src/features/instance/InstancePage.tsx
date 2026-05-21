import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import { ErrorCard } from '@/components/ErrorCard'
import { StatusPill } from '@/components/StatusPill'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useSSE } from '@/hooks/useSSE'
import { MetricsTab } from '@/features/metrics/MetricsTab'
import { InstanceControls } from './InstanceControls'
import { InstanceChat } from './InstanceChat'
import { LogsView } from './LogsView'

type InstanceState = {
  running: boolean
  config_id?: string
  mode?: string
  port?: number
}

export function InstancePage() {
  const queryClient = useQueryClient()
  const instance = useQuery({
    queryKey: ['instance'],
    queryFn: async () => {
      const { data, error } = await api.GET('/instance')
      if (error) throw new Error('Failed to load instance')
      return data as InstanceState
    },
  })

  const stream = useSSE<InstanceState>({
    url: '/api/instance/stream',
    enabled: true,
  })

  useEffect(() => {
    if (stream.event) {
      queryClient.setQueryData(['instance'], stream.event)
    }
  }, [stream.event, queryClient])

  if (instance.isPending) return <Skeleton className="h-64 w-full" />
  if (instance.isError) return <ErrorCard title="Failed to load instance" message={String(instance.error)} />

  const state = (stream.event ?? instance.data)! as InstanceState

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Instance</h1>
        {state.running && <StatusPill instance={state} />}
      </div>

      <InstanceControls />

      {state.running && (
        <>
          <Card className="p-4">
            <dl className="text-sm space-y-2">
              <div className="flex gap-4">
                <dt className="font-mono text-zinc-500 w-32">config</dt>
                <dd>{state.config_id}</dd>
              </div>
              <div className="flex gap-4">
                <dt className="font-mono text-zinc-500 w-32">mode</dt>
                <dd>{state.mode ?? '—'}</dd>
              </div>
              {state.port != null && (
                <div className="flex gap-4">
                  <dt className="font-mono text-zinc-500 w-32">port</dt>
                  <dd>{state.port}</dd>
                </div>
              )}
            </dl>
          </Card>

          <InstanceChat configId={state.config_id!} port={state.port} />

          <Tabs defaultValue="logs">
            <TabsList>
              <TabsTrigger value="logs">Logs</TabsTrigger>
              <TabsTrigger value="metrics">Metrics</TabsTrigger>
            </TabsList>
            <TabsContent value="logs">
              <LogsView enabled={state.running} />
            </TabsContent>
            <TabsContent value="metrics">
              <MetricsTab configId={state.config_id!} />
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  )
}
