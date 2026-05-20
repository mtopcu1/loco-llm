import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import { api } from '@/api/client'
import { Plan2Button } from '@/components/Plan2Button'
import { ErrorCard } from '@/components/ErrorCard'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ParamsView } from './ParamsView'

export function ConfigDetailPage() {
  const { id } = useParams({ from: '/configs/$id' })
  const config = useQuery({
    queryKey: ['configs', id],
    queryFn: async () => {
      const { data, error } = await api.GET('/configs/{config_id}', {
        params: { path: { config_id: id } },
      })
      if (error) throw new Error('Failed to load config')
      return data as Record<string, unknown>
    },
  })

  const validate = useQuery({
    queryKey: ['configs', id, 'validate'],
    queryFn: async () => {
      const { data, error } = await api.GET('/configs/{config_id}/validate', {
        params: { path: { config_id: id } },
      })
      if (error) throw new Error('Validation failed')
      return data as { valid: boolean; errors: string[] }
    },
    enabled: false,
  })

  if (config.isPending) return <Skeleton className="h-64 w-full" />
  if (config.isError) return <ErrorCard title="Failed to load config" message={String(config.error)} />

  const cfg = config.data!

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <Link to="/configs" className="text-sm text-zinc-500 hover:underline">
            ← Configs
          </Link>
          <h1 className="text-2xl font-semibold font-mono mt-1">{String(cfg.id)}</h1>
          <p className="text-sm text-zinc-500">source: {String(cfg.source ?? '—')}</p>
        </div>
        <Plan2Button size="sm">Edit</Plan2Button>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="params">Params</TabsTrigger>
          <TabsTrigger value="validate">Validate</TabsTrigger>
          <TabsTrigger value="raw">Raw YAML</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          <pre className="text-sm bg-zinc-50 p-3 rounded border overflow-x-auto">
            {JSON.stringify(cfg.resolved ?? cfg.raw, null, 2)}
          </pre>
        </TabsContent>
        <TabsContent value="params">
          <ParamsView configId={id} />
        </TabsContent>
        <TabsContent value="validate" className="space-y-4">
          <Button onClick={() => validate.refetch()} disabled={validate.isFetching}>
            {validate.isFetching ? 'Validating…' : 'Run validation'}
          </Button>
          {validate.data && (
            <div className={validate.data.valid ? 'text-green-700' : 'text-red-700'}>
              {validate.data.valid ? 'Valid' : 'Invalid'}
              {validate.data.errors.length > 0 && (
                <ul className="mt-2 list-disc pl-5 text-sm">
                  {validate.data.errors.map((err) => (
                    <li key={err}>{err}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {validate.isError && (
            <p className="text-red-700 text-sm">Validation request failed.</p>
          )}
        </TabsContent>
        <TabsContent value="raw">
          <pre className="text-sm bg-zinc-50 p-3 rounded border overflow-x-auto">
            {JSON.stringify(cfg.raw, null, 2)}
          </pre>
        </TabsContent>
      </Tabs>
    </div>
  )
}
