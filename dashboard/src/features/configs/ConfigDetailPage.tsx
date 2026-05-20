import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { errorToToast } from '@/lib/errorToToast'
import { ErrorCard } from '@/components/ErrorCard'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ConfigForm } from './ConfigForm'
import { ParamsView } from './ParamsView'
import { PerformanceMetricsCard } from '@/features/metrics/PerformanceMetricsCard'

export function ConfigDetailPage() {
  const { id } = useParams({ from: '/configs/$id' })
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)

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

  const remove = useMutation({
    mutationFn: async () => {
      const { error } = await api.DELETE('/configs/{config_id}', {
        params: { path: { config_id: id } },
      })
      if (error) throw error
    },
    onSuccess: () => {
      toast.success('Config deleted')
      void navigate({ to: '/configs' })
      void qc.invalidateQueries({ queryKey: ['configs'] })
    },
    onError: errorToToast,
  })

  if (config.isPending) return <Skeleton className="h-64 w-full" />
  if (config.isError) return <ErrorCard title="Failed to load config" message={String(config.error)} />

  const cfg = config.data!
  const raw = (cfg.raw ?? cfg.resolved) as Record<string, unknown>
  const serve = raw.serve as { params?: Record<string, unknown> } | undefined

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
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setEditing((e) => !e)}>
            {editing ? 'Cancel edit' : 'Edit'}
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => {
              if (!window.confirm(`Delete config "${id}"?`)) return
              remove.mutate()
            }}
          >
            Delete
          </Button>
        </div>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="params">Params</TabsTrigger>
          <TabsTrigger value="validate">Validate</TabsTrigger>
          <TabsTrigger value="raw">Raw YAML</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          {editing ? (
            <ConfigForm
              mode="update"
              initial={{
                id: String(cfg.id),
                runtime: String(raw.runtime ?? ''),
                model: raw.model ? String(raw.model) : undefined,
                serve,
              }}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <div className="space-y-4">
              <PerformanceMetricsCard configId={id} />
              <pre className="text-sm bg-zinc-50 p-3 rounded border overflow-x-auto">
                {JSON.stringify(cfg.resolved ?? cfg.raw, null, 2)}
              </pre>
            </div>
          )}
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
          {editing ? (
            <ConfigForm
              mode="update"
              initial={{
                id: String(cfg.id),
                runtime: String(raw.runtime ?? ''),
                model: raw.model ? String(raw.model) : undefined,
                serve,
              }}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <pre className="text-sm bg-zinc-50 p-3 rounded border overflow-x-auto">
              {JSON.stringify(cfg.raw, null, 2)}
            </pre>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
