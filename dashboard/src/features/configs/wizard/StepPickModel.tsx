import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { Skeleton } from '@/components/ui/skeleton'
import { useWizard } from './WizardContext'

type ModelRow = { id: string; format?: string }

function acceptsFormats(manifest: Record<string, unknown> | undefined): string[] {
  const raw = manifest?.accepts_formats
  if (!Array.isArray(raw)) return []
  return raw.map(String)
}

export function StepPickModel() {
  const { state, dispatch } = useWizard()
  const runtimeId = state.runtimeId!

  const runtime = useQuery({
    queryKey: ['runtimes', runtimeId],
    queryFn: async () => {
      const { data, error } = await api.GET('/runtimes/{runtime_id}', {
        params: { path: { runtime_id: runtimeId } },
      })
      if (error) throw new Error('Failed to load runtime')
      return data as { manifest?: Record<string, unknown> }
    },
    enabled: !!runtimeId,
  })

  const models = useQuery({
    queryKey: ['models'],
    queryFn: async () => {
      const { data, error } = await api.GET('/models')
      if (error) throw new Error('Failed to load models')
      return (data ?? []) as ModelRow[]
    },
  })

  if (runtime.isPending || models.isPending) return <Skeleton className="h-10 w-full max-w-md" />
  if (runtime.isError || models.isError) {
    return <p className="text-sm text-red-600">Failed to load models for this runtime.</p>
  }

  const formats = acceptsFormats(runtime.data?.manifest)
  const modelOptional = formats.length === 0
  const filtered =
    formats.length === 0
      ? models.data!
      : models.data!.filter((m) => m.format && formats.includes(m.format))

  const selectValue = state.modelId === null ? '__skip__' : (state.modelId ?? '')

  return (
    <div className="space-y-4 max-w-md">
      <p className="text-sm text-zinc-600">
        {modelOptional
          ? 'This runtime does not require a model. You may skip or pick one.'
          : `Select a model (${formats.join(', ')}).`}
      </p>
      <select
        aria-label="Model"
        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs"
        value={selectValue}
        onChange={(e) => {
          const v = e.target.value
          dispatch({ type: 'setModel', modelId: v === '__skip__' ? null : v })
        }}
      >
        {modelOptional && <option value="__skip__">Skip — no model</option>}
        {!modelOptional && <option value="">Select a model…</option>}
        {filtered.map((m) => (
          <option key={m.id} value={m.id}>
            {m.id}
            {m.format ? ` (${m.format})` : ''}
          </option>
        ))}
      </select>
      {!modelOptional && filtered.length === 0 && (
        <p className="text-sm text-amber-700">No compatible models installed for this runtime.</p>
      )}
    </div>
  )
}
