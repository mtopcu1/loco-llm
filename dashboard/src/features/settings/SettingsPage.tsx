import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { ErrorCard } from '@/components/ErrorCard'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { SettingsForm } from './SettingsForm'

type SettingsData = {
  stored: Record<string, unknown>
  resolved: Record<string, unknown>
  registry: Array<{ key: string; kind?: string; label?: string }>
}

export function SettingsPage() {
  const settings = useQuery({
    queryKey: ['settings'],
    queryFn: async () => {
      const { data, error } = await api.GET('/settings')
      if (error) throw new Error('Failed to load settings')
      return data as SettingsData
    },
  })

  if (settings.isPending) return <Skeleton className="h-64 w-full" />
  if (settings.isError) return <ErrorCard title="Failed to load settings" message={String(settings.error)} />

  const s = settings.data!

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <SettingsForm registry={s.registry} stored={s.stored} />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-4">
          <h2 className="font-medium mb-3">Stored</h2>
          <dl className="text-sm space-y-2">
            {Object.entries(s.stored).map(([key, value]) => (
              <div key={key} className="flex gap-4">
                <dt className="font-mono text-zinc-500 w-32">{key}</dt>
                <dd className="break-all">{String(value ?? '—')}</dd>
              </div>
            ))}
          </dl>
        </Card>
        <Card className="p-4">
          <h2 className="font-medium mb-3">Resolved</h2>
          <dl className="text-sm space-y-2">
            {Object.entries(s.resolved).map(([key, value]) => (
              <div key={key} className="flex gap-4">
                <dt className="font-mono text-zinc-500 w-32">{key}</dt>
                <dd className="break-all">{String(value ?? '—')}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>
    </div>
  )
}
