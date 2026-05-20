import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { getApiError } from '@/lib/apiError'
import { errorToToast } from '@/lib/errorToToast'
import { Skeleton } from '@/components/ui/skeleton'
import { ParamGrid } from '@/features/params/ParamGrid'
import type { ParamCell, Recommendation } from '@/lib/paramCell'

export function ParamsView({ configId }: { configId: string }) {
  const qc = useQueryClient()
  const [saveErrors, setSaveErrors] = useState<string[]>([])

  const config = useQuery({
    queryKey: ['configs', configId],
    queryFn: async () => {
      const { data, error } = await api.GET('/configs/{config_id}', {
        params: { path: { config_id: configId } },
      })
      if (error) throw new Error('Failed to load config')
      return data as {
        id: string
        raw?: Record<string, unknown>
        resolved?: Record<string, unknown>
      }
    },
  })

  const params = useQuery({
    queryKey: ['configs', configId, 'params'],
    queryFn: async () => {
      const { data, error } = await api.GET('/configs/{config_id}/params', {
        params: { path: { config_id: configId } },
      })
      if (error) throw new Error('Failed to load params')
      return data as ParamCell[]
    },
  })

  const raw = (config.data?.raw ?? config.data?.resolved) as Record<string, unknown> | undefined
  const runtimeId = raw?.runtime ? String(raw.runtime) : ''
  const modelId = raw?.model ? String(raw.model) : undefined

  const recommendations = useQuery({
    queryKey: ['recommendations', runtimeId, modelId ?? ''],
    queryFn: async () => {
      const { data, error } = await api.GET('/recommendations', {
        params: { query: { runtime_id: runtimeId, model_id: modelId ?? null } },
      })
      if (error) throw new Error('Failed to load recommendations')
      return data as Recommendation[]
    },
    enabled: Boolean(runtimeId),
  })

  const save = useMutation({
    mutationFn: async (serveParams: Record<string, unknown>) => {
      setSaveErrors([])
      if (!config.data) throw new Error('Config not loaded')
      const cfgRaw = (config.data.raw ?? config.data.resolved) as Record<string, unknown>
      const serve =
        typeof cfgRaw.serve === 'object' && cfgRaw.serve
          ? (cfgRaw.serve as Record<string, unknown>)
          : {}
      const body = {
        ...cfgRaw,
        id: configId,
        serve: { ...serve, params: serveParams },
      }
      const { error } = await api.PUT('/configs/{config_id}', {
        params: { path: { config_id: configId } },
        body,
      })
      if (error) throw error
    },
    onSuccess: () => {
      toast.success('Params saved')
      void qc.invalidateQueries({ queryKey: ['configs', configId] })
      void qc.invalidateQueries({ queryKey: ['configs', configId, 'params'] })
    },
    onError: (err) => {
      const apiErr = getApiError(err)
      if (apiErr?.code === 'CONFIG_INVALID') {
        const errors = apiErr.details?.errors
        setSaveErrors(Array.isArray(errors) ? errors.map(String) : [apiErr.message])
        return
      }
      errorToToast(err)
    },
  })

  if (config.isPending || params.isPending) {
    return <Skeleton className="h-64 w-full" data-testid="params-loading" />
  }
  if (config.isError || params.isError) {
    return <p>Failed to load params.</p>
  }

  return (
    <ParamGrid
      cells={params.data ?? []}
      recommendations={recommendations.data ?? []}
      onSave={async (serveParams) => {
        await save.mutateAsync(serveParams)
      }}
      saveErrors={saveErrors}
      saving={save.isPending}
    />
  )
}
