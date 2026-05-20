import { Card } from '@/components/ui/card'
import type { Snapshot } from '@/hooks/useMetricsStream'

export interface MetricFieldMeta {
  label: string
  unit?: string
}

export function formatMetricValue(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  if (Math.abs(value) >= 100) return value.toFixed(0)
  if (Math.abs(value) >= 10) return value.toFixed(1)
  return value.toFixed(2)
}

export function metricFieldsFromSnapshot(snapshot: Snapshot | null): string[] {
  if (!snapshot || snapshot.error) return []
  return Object.keys(snapshot).filter(
    (key) => key !== 'ts' && typeof snapshot[key] === 'number',
  )
}

export interface MetricsCardsProps {
  snapshot: Snapshot | null
  fieldMeta?: Record<string, MetricFieldMeta>
}

export function MetricsCards({ snapshot, fieldMeta }: MetricsCardsProps) {
  const fields = metricFieldsFromSnapshot(snapshot)
  if (fields.length === 0) {
    return <p className="text-sm text-zinc-500">Waiting for metrics…</p>
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {fields.map((field) => {
        const meta = fieldMeta?.[field]
        const label = meta?.label ?? field.replace(/_/g, ' ')
        const unit = meta?.unit
        const value = snapshot![field] as number
        return (
          <Card key={field} className="p-4">
            <p className="text-sm text-zinc-500">{label}</p>
            <p className="text-3xl font-semibold tabular-nums">
              {formatMetricValue(value)}
              {unit ? (
                <span className="text-base font-normal text-zinc-500 ml-1">{unit}</span>
              ) : null}
            </p>
          </Card>
        )
      })}
    </div>
  )
}
