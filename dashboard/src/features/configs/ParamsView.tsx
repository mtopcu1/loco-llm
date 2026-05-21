import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { unwrapApi } from '@/api/helpers'
import { useConfigDocument } from '@/hooks/useConfigDocument'
import { buildConfigPutBody } from '@/lib/configDocument'
import { getApiError } from '@/lib/apiError'
import { errorToToast } from '@/lib/errorToToast'
import { Skeleton } from '@/components/ui/skeleton'
import { ParamGrid } from '@/features/params/ParamGrid'
import type { ParamCell, Recommendation } from '@/lib/paramCell'

export function ParamsView({ configId }: { configId: string }) {
  const qc = useQueryClient()
  const [saveErrors, setSaveErrors] = useState<string[]>([])

  const config = useConfigDocument(configId)

  const params = useQuery({
    queryKey: ['configs', configId, 'params'],
    queryFn: async () => {
      const data = await unwrapApi(() =>
        api.GET('/configs/{config_id}/params', {
          params: { path: { config_id: configId } },
        }),
      )
      return data as ParamCell[]
    },
  })

  const runtimeId = config.data?.runtimeId ?? ''
  const modelId = config.data?.modelId

  const recommendations = useQuery({
    queryKey: ['recommendations', runtimeId, modelId ?? ''],
    queryFn: async () => {
      const data = await unwrapApi(() =>
        api.GET('/recommendations', {
          params: { query: { runtime_id: runtimeId, model_id: modelId ?? null } },
        }),
      )
      return data as Recommendation[]
    },
    enabled: Boolean(runtimeId),
  })

  const save = useMutation({
    mutationFn: async (serveParams: Record<string, unknown>) => {
      setSaveErrors([])
      if (!config.data) throw new Error('Config not loaded')
      const body = buildConfigPutBody(configId, config.data.detail, serveParams)
      await unwrapApi(() =>
        api.PUT('/configs/{config_id}', {
          params: { path: { config_id: configId } },
          body,
        }),
      )
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
