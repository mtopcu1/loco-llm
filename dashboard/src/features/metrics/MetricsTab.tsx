import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { unwrapApi } from '@/api/helpers'
import { useConfigDocument } from '@/hooks/useConfigDocument'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useMetricsStream } from '@/hooks/useMetricsStream'
import {
  MetricsCards,
  metricFieldsFromSnapshot,
  type MetricFieldMeta,
} from './MetricsCards'
import { Sparkline } from './Sparkline'

function fieldMetaFromManifest(
  manifest: Record<string, unknown> | undefined,
): Record<string, MetricFieldMeta> {
  const metrics = manifest?.metrics as { fields?: Record<string, { label?: string; unit?: string }> } | null | undefined
  if (!metrics?.fields) return {}
  const out: Record<string, MetricFieldMeta> = {}
  for (const [id, spec] of Object.entries(metrics.fields)) {
    out[id] = { label: spec.label ?? id, unit: spec.unit }
  }
  return out
}

export interface MetricsTabProps {
  configId: string
}

export function MetricsTab({ configId }: MetricsTabProps) {
  const config = useConfigDocument(configId)
  const runtimeId = config.data?.runtimeId || null

  const runtime = useQuery({
    queryKey: ['runtimes', runtimeId],
    queryFn: async () => {
      const data = await unwrapApi(() =>
        api.GET('/runtimes/{runtime_id}', {
          params: { path: { runtime_id: runtimeId! } },
        }),
      )
      return data as { manifest: Record<string, unknown>; id: string }
    },
    enabled: runtimeId != null,
  })

  const runtimes = useQuery({
    queryKey: ['runtimes'],
    queryFn: async () => {
      const data = await unwrapApi(() => api.GET('/runtimes'))
      return data as Array<{ id: string; has_metrics: boolean }>
    },
  })

  const hasMetrics = useMemo(() => {
    if (runtimeId == null) return false
    const summary = runtimes.data?.find((rt) => rt.id === runtimeId)
    if (summary != null) return summary.has_metrics
    return Boolean(runtime.data?.manifest?.metrics)
  }, [runtimeId, runtimes.data, runtime.data])

  const fieldMeta = useMemo(
    () => fieldMetaFromManifest(runtime.data?.manifest),
    [runtime.data?.manifest],
  )

  const { latest, buffer, connected } = useMetricsStream(hasMetrics)
  const [disconnectedLong, setDisconnectedLong] = useState(false)

  useEffect(() => {
    if (connected) {
      setDisconnectedLong(false)
      return
    }
    const timer = setTimeout(() => setDisconnectedLong(true), 10_000)
    return () => clearTimeout(timer)
  }, [connected])

  if (config.isPending || runtimes.isPending) {
    return <Skeleton className="h-48 w-full" />
  }

  if (!hasMetrics) {
    return (
      <Card className="p-4">
        <p className="text-sm text-zinc-600">This runtime does not expose live metrics.</p>
      </Card>
    )
  }

  const fields = metricFieldsFromSnapshot(latest)
  const sparkFields = fields.length > 0
    ? fields
    : Object.keys(fieldMeta)

  return (
    <div className="space-y-6">
      {disconnectedLong ? (
        <p className="text-amber-600 text-sm">Metrics stream disconnected — retrying…</p>
      ) : null}
      <MetricsCards snapshot={latest} fieldMeta={fieldMeta} />
      {sparkFields.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {sparkFields.map((field) => {
            const values = buffer
              .map((snap) => snap[field])
              .filter((v): v is number => typeof v === 'number')
            const label = fieldMeta[field]?.label ?? field.replace(/_/g, ' ')
            return (
              <Card key={field} className="p-4">
                <p className="text-sm text-zinc-500 mb-2">{label}</p>
                <Sparkline values={values} width={240} height={48} color="#2563eb" />
              </Card>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}
