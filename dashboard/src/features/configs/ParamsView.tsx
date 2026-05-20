import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'

export function ParamsView({ configId }: { configId: string }) {
  const q = useQuery({
    queryKey: ['configs', configId, 'params'],
    queryFn: async () => {
      const { data, error } = await api.GET('/configs/{config_id}/params', {
        params: { path: { config_id: configId } },
      })
      if (error) throw new Error('Failed to load params')
      return data
    },
  })

  if (q.isPending) return <p>Loading…</p>
  if (q.isError) return <p>Failed to load params.</p>

  return (
    <div className="text-xs text-zinc-500 mb-2">
      Read-only view. Editing arrives in Plan 3.
      <pre className="mt-2 text-sm bg-zinc-50 p-3 rounded border overflow-x-auto text-zinc-900">
        {JSON.stringify(q.data, null, 2)}
      </pre>
    </div>
  )
}
