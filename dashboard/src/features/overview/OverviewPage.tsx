import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorCard } from '@/components/ErrorCard'
import { formatMetricValue } from '@/features/metrics/MetricsCards'
import { useMetricsStream } from '@/hooks/useMetricsStream'

type OverviewData = {
  instance: { running: boolean; config_id?: string }
  runtimes_count: number
  runtimes_installed_count: number
  models_count: number
  configs_count: number
  doctor_summary: Record<string, { ok: number; warning: number; error: number }>
  disk_summary: { data_root_pct_used: number }
}

export function OverviewPage() {
  const overview = useQuery({
    queryKey: ['overview'],
    queryFn: async () => {
      const { data, error } = await api.GET('/overview')
      if (error) throw new Error('Failed to load overview')
      return data as OverviewData
    },
  })

  if (overview.isPending) return <Skeleton className="h-96 w-full" />
  if (overview.isError) return <ErrorCard title="Failed to load" message={String(overview.error)} />

  const o = overview.data!
  const metrics = useMetricsStream(o.instance.running)

  const liveTps =
    metrics.latest && typeof metrics.latest.tps_decode === 'number'
      ? formatMetricValue(metrics.latest.tps_decode)
      : '—'
  const liveTtft =
    metrics.latest && typeof metrics.latest.ttft_ms === 'number'
      ? formatMetricValue(metrics.latest.ttft_ms)
      : '—'

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Overview</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4">
          <h3 className="text-sm text-zinc-500">Instance</h3>
          <p className="text-lg">
            {o.instance.running ? `Running: ${o.instance.config_id}` : 'idle'}
          </p>
          {o.instance.running ? (
            <div className="mt-2 flex gap-3 text-sm">
              <span className="rounded bg-blue-50 px-2 py-0.5 text-blue-800 tabular-nums">
                TPS {liveTps}
              </span>
              <span className="rounded bg-blue-50 px-2 py-0.5 text-blue-800 tabular-nums">
                TTFT {liveTtft} ms
              </span>
            </div>
          ) : null}
        </Card>
        <Card className="p-4">
          <h3 className="text-sm text-zinc-500">Catalog</h3>
          <p>
            {o.runtimes_installed_count}/{o.runtimes_count} runtimes installed
            <br />
            {o.models_count} models · {o.configs_count} configs
          </p>
        </Card>
        <Card className="p-4">
          <h3 className="text-sm text-zinc-500">Disk</h3>
          <p>{Math.round(o.disk_summary.data_root_pct_used)}% of data_root used</p>
        </Card>
      </div>

      <Card className="p-4">
        <h3 className="font-medium mb-2">Doctor</h3>
        <ul className="space-y-1 text-sm">
          {Object.entries(o.doctor_summary).map(([scope, s]) => (
            <li key={scope}>
              <span className="font-mono">{scope}</span>: {s.ok} ok, {s.warning} warn, {s.error} err
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
