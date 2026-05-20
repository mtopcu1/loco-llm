import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { buildConfigBody } from '@/lib/paramCell'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ParamGrid } from '@/features/params/ParamGrid'
import { useWizard } from './WizardContext'

export function StepReview() {
  const { state, dispatch } = useWizard()

  const configs = useQuery({
    queryKey: ['configs'],
    queryFn: async () => {
      const { data, error } = await api.GET('/configs')
      if (error) throw new Error('Failed to load configs')
      return (data ?? []) as Array<{ id: string }>
    },
  })

  if (configs.isPending) return <Skeleton className="h-64 w-full" />
  if (configs.isError) return <p className="text-sm text-red-600">Failed to verify config ID.</p>

  const ids = new Set(configs.data!.map((c) => c.id))
  const idTaken = state.configId.trim() !== '' && ids.has(state.configId)
  const preview = state.runtimeId && state.params
    ? buildConfigBody({
        configId: state.configId,
        runtimeId: state.runtimeId,
        modelId: state.modelId,
        params: state.params,
      })
    : null

  return (
    <div className="space-y-6">
      <div className="max-w-md space-y-2">
        <label className="text-sm font-medium" htmlFor="wizard-config-id">
          Config ID
        </label>
        <Input
          id="wizard-config-id"
          value={state.configId}
          onChange={(e) => dispatch({ type: 'setConfigId', configId: e.target.value })}
          className="font-mono"
        />
        {idTaken && (
          <p className="text-sm text-red-600">A config with this ID already exists.</p>
        )}
      </div>

      {state.params && (
        <div>
          <h3 className="text-sm font-medium mb-2">Parameters</h3>
          <ParamGrid cells={state.params} recommendations={[]} mode="review" />
        </div>
      )}

      {preview && (
        <div>
          <h3 className="text-sm font-medium mb-2">Config preview</h3>
          <pre className="text-sm bg-zinc-50 p-3 rounded border overflow-x-auto">
            {JSON.stringify(preview, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

export function reviewBlocksAdvance(state: { configId: string }, idTaken: boolean): boolean {
  return idTaken || !state.configId.trim()
}
