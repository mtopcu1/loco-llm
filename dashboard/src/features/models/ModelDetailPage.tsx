import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import { api } from '@/api/client'
import { ErrorCard } from '@/components/ErrorCard'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { formatBytes } from '@/lib/format'

export function ModelDetailPage() {
  const { id } = useParams({ from: '/models/$id' })
  const model = useQuery({
    queryKey: ['models', id],
    queryFn: async () => {
      const { data, error } = await api.GET('/models/{model_id}', {
        params: { path: { model_id: id } },
      })
      if (error) throw new Error('Failed to load model')
      return data as Record<string, unknown>
    },
  })

  if (model.isPending) return <Skeleton className="h-64 w-full" />
  if (model.isError) return <ErrorCard title="Failed to load model" message={String(model.error)} />

  const m = model.data!
  const artifact = m.artifact as { total_size_bytes?: number } | undefined

  return (
    <div className="space-y-6">
      <div>
        <Link to="/models" className="text-sm text-zinc-500 hover:underline">
          ← Models
        </Link>
        <h1 className="text-2xl font-semibold font-mono mt-1">{String(m.id)}</h1>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="raw">Raw JSON</TabsTrigger>
        </TabsList>
        <TabsContent value="overview" className="space-y-4">
          <dl className="text-sm space-y-2">
            <div className="flex gap-4">
              <dt className="font-mono text-zinc-500 w-40">format</dt>
              <dd>{String(m.format ?? '—')}</dd>
            </div>
            {artifact?.total_size_bytes != null && (
              <div className="flex gap-4">
                <dt className="font-mono text-zinc-500 w-40">size</dt>
                <dd>{formatBytes(artifact.total_size_bytes)}</dd>
              </div>
            )}
            <div className="flex gap-4">
              <dt className="font-mono text-zinc-500 w-40">installed_at</dt>
              <dd>{String(m.installed_at ?? '—')}</dd>
            </div>
          </dl>
        </TabsContent>
        <TabsContent value="raw">
          <pre className="text-sm bg-zinc-50 p-3 rounded border overflow-x-auto">
            {JSON.stringify(m, null, 2)}
          </pre>
        </TabsContent>
      </Tabs>
    </div>
  )
}
