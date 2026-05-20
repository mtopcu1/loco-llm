import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { formatDuration } from '@/lib/format'
import { formatMetricValue } from '@/features/metrics/MetricsCards'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

type AggregateMetrics = Record<string, number>

function aggregateFieldKeys(data: AggregateMetrics): string[] {
  const prefixes = new Set<string>()
  for (const key of Object.keys(data)) {
    for (const prefix of ['avg_', 'p50_', 'p95_'] as const) {
      if (key.startsWith(prefix)) {
        prefixes.add(key.slice(prefix.length))
      }
    }
  }
  return [...prefixes].sort()
}

export function PerformanceMetricsCard({ configId }: { configId: string }) {
  const metrics = useQuery({
    queryKey: ['configs', configId, 'metrics', 'aggregate'],
    queryFn: async () => {
      const { data, error } = await api.GET('/configs/{config_id}/metrics/aggregate', {
        params: { path: { config_id: configId }, query: { window: '7d' } },
      })
      if (error) throw new Error('Failed to load metrics')
      return data as AggregateMetrics
    },
  })

  if (metrics.isPending) return <Skeleton className="h-40 w-full" />
  if (metrics.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Performance</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-red-700">Failed to load aggregated metrics.</p>
        </CardContent>
      </Card>
    )
  }

  const data = metrics.data!
  if (!data.samples) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Performance</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-zinc-500">No metrics yet — run this config to collect data.</p>
        </CardContent>
      </Card>
    )
  }

  const fields = aggregateFieldKeys(data)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Performance</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-zinc-500">Samples (7d)</dt>
            <dd className="font-mono text-lg">{data.samples}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Total uptime</dt>
            <dd className="font-mono text-lg">
              {formatDuration(data.total_uptime_seconds ?? 0)}
            </dd>
          </div>
        </dl>
        {fields.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-zinc-500 border-b">
                  <th className="pb-2 pr-4 font-normal">Metric</th>
                  <th className="pb-2 pr-4 font-normal">Avg</th>
                  <th className="pb-2 pr-4 font-normal">P50</th>
                  <th className="pb-2 font-normal">P95</th>
                </tr>
              </thead>
              <tbody>
                {fields.map((field) => (
                  <tr key={field} className="border-b last:border-0">
                    <td className="py-2 pr-4 font-mono">{field.replace(/_/g, ' ')}</td>
                    <td className="py-2 pr-4 tabular-nums">{formatMetricValue(data[`avg_${field}`])}</td>
                    <td className="py-2 pr-4 tabular-nums">{formatMetricValue(data[`p50_${field}`])}</td>
                    <td className="py-2 tabular-nums">{formatMetricValue(data[`p95_${field}`])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
