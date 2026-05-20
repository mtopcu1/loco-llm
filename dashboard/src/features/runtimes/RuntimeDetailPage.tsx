import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import { api } from '@/api/client'
import { ErrorCard } from '@/components/ErrorCard'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

export function RuntimeDetailPage() {
  const { id } = useParams({ from: '/runtimes/$id' })
  const runtime = useQuery({
    queryKey: ['runtimes', id],
    queryFn: async () => {
      const { data, error } = await api.GET('/runtimes/{runtime_id}', {
        params: { path: { runtime_id: id } },
      })
      if (error) throw new Error('Failed to load runtime')
      return data
    },
  })

  if (runtime.isPending) return <Skeleton className="h-64 w-full" />
  if (runtime.isError) return <ErrorCard title="Failed to load runtime" message={String(runtime.error)} />

  const rt = runtime.data!

  return (
    <div className="space-y-6">
      <div>
        <Link to="/runtimes" className="text-sm text-zinc-500 hover:underline">
          ← Runtimes
        </Link>
        <h1 className="text-2xl font-semibold font-mono mt-1">{rt.id}</h1>
        <p className="text-sm text-zinc-500">{rt.kind}</p>
      </div>

      <Tabs defaultValue="manifest">
        <TabsList>
          <TabsTrigger value="manifest">Manifest</TabsTrigger>
          <TabsTrigger value="install">Install record</TabsTrigger>
          <TabsTrigger value="drift">Drift</TabsTrigger>
        </TabsList>
        <TabsContent value="manifest">
          <pre className="text-sm bg-zinc-50 p-3 rounded border overflow-x-auto">
            {JSON.stringify(rt.manifest, null, 2)}
          </pre>
        </TabsContent>
        <TabsContent value="install">
          {rt.install_record ? (
            <dl className="text-sm space-y-2">
              {Object.entries(rt.install_record).map(([key, value]) => (
                <div key={key} className="flex gap-4">
                  <dt className="font-mono text-zinc-500 w-40">{key}</dt>
                  <dd>{String(value)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-zinc-500">Not installed</p>
          )}
        </TabsContent>
        <TabsContent value="drift">
          {rt.drift ? (
            <dl className="text-sm space-y-2">
              {Object.entries(rt.drift).map(([key, value]) => (
                <div key={key} className="flex gap-4">
                  <dt className="font-mono text-zinc-500 w-40">{key}</dt>
                  <dd>{String(value)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-zinc-500">Not installed</p>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
