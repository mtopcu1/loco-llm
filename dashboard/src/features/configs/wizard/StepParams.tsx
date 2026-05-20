import { forwardRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { ParamCell, Recommendation } from '@/lib/paramCell'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ParamGrid, type ParamGridHandle } from '@/features/params/ParamGrid'
import { useWizard } from './WizardContext'

export const StepParams = forwardRef<ParamGridHandle>(function StepParams(_props, ref) {
  const { state } = useWizard()
  const runtimeId = state.runtimeId!
  const modelId = state.modelId

  const defaults = useQuery({
    queryKey: ['runtimes', runtimeId, 'default-params', modelId],
    queryFn: async () => {
      const { data, error } = await api.GET('/runtimes/{runtime_id}/default-params', {
        params: {
          path: { runtime_id: runtimeId },
          query: modelId ? { model_id: modelId } : {},
        },
      })
      if (error) throw new Error('Failed to load default params')
      return (data ?? []) as ParamCell[]
    },
    enabled: !!runtimeId,
  })

  const recommendations = useQuery({
    queryKey: ['recommendations', runtimeId, modelId],
    queryFn: async () => {
      const { data, error } = await api.GET('/recommendations', {
        params: {
          query: {
            runtime_id: runtimeId,
            ...(modelId ? { model_id: modelId } : {}),
          },
        },
      })
      if (error) throw new Error('Failed to load recommendations')
      return (data ?? []) as Recommendation[]
    },
    enabled: !!runtimeId,
  })

  if (defaults.isPending || recommendations.isPending) {
    return <Skeleton className="h-64 w-full" />
  }
  if (defaults.isError || recommendations.isError) {
    return <p className="text-sm text-red-600">Failed to load parameters.</p>
  }

  const recs = recommendations.data ?? []
  const topRecs = [...recs]
    .sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0))
    .slice(0, 3)

  const cells = state.params ?? defaults.data!

  return (
    <div className="space-y-4">
      {recs.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Advisor</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <ul className="text-sm text-zinc-600 space-y-1">
              {topRecs.map((r) => (
                <li key={r.param_key}>
                  <span className="font-mono">{r.param_key}</span> → {String(r.suggested_value)}:{' '}
                  {r.reason}
                </li>
              ))}
            </ul>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                if (typeof ref !== 'function' && ref?.current) {
                  ref.current.applyAllSuggestions(recs)
                }
              }}
            >
              Apply all suggestions
            </Button>
          </CardContent>
        </Card>
      )}
      <ParamGrid ref={ref} cells={cells} recommendations={recs} mode="edit" />
    </div>
  )
})
