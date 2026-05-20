import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { Skeleton } from '@/components/ui/skeleton'
import { useWizard } from './WizardContext'

type RuntimeRow = {
  id: string
  kind: string
  installed: boolean
}

export function StepPickRuntime() {
  const { state, dispatch } = useWizard()

  const runtimes = useQuery({
    queryKey: ['runtimes'],
    queryFn: async () => {
      const { data, error } = await api.GET('/runtimes')
      if (error) throw new Error('Failed to load runtimes')
      return (data ?? []) as RuntimeRow[]
    },
  })

  if (runtimes.isPending) return <Skeleton className="h-10 w-full max-w-md" />
  if (runtimes.isError) return <p className="text-sm text-red-600">Failed to load runtimes.</p>

  const installed = runtimes.data!.filter((rt) => rt.installed)

  return (
    <div className="space-y-4 max-w-md">
      <p className="text-sm text-zinc-600">Choose which runtime this config will use.</p>
      <select
        aria-label="Runtime"
        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs"
        value={state.runtimeId ?? ''}
        onChange={(e) => {
          const runtimeId = e.target.value
          if (runtimeId) dispatch({ type: 'setRuntime', runtimeId })
        }}
      >
        <option value="">Select a runtime…</option>
        {runtimes.data!.map((rt) => (
          <option key={rt.id} value={rt.id} disabled={!rt.installed}>
            {rt.id}
            {!rt.installed ? ' (install first)' : ''}
          </option>
        ))}
      </select>
      {installed.length === 0 && (
        <p className="text-sm text-amber-700">No installed runtimes. Install one from the Runtimes page.</p>
      )}
    </div>
  )
}
