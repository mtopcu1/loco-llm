import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { buildConfigBody } from '@/lib/paramCell'
import type { ApiErrorBody } from '@/lib/apiError'
import { getApiError } from '@/lib/apiError'
import { Button } from '@/components/ui/button'
import { useWizard } from './WizardContext'

function extractApiError(err: unknown): ApiErrorBody | null {
  const wrapped = getApiError(err)
  if (wrapped) return wrapped
  if (err && typeof err === 'object' && 'code' in err) {
    return err as ApiErrorBody
  }
  return null
}

export function StepSave() {
  const { state, dispatch } = useWizard()
  const navigate = useNavigate()
  const [inlineError, setInlineError] = useState<string | null>(null)

  const save = useMutation({
    mutationFn: async () => {
      if (!state.runtimeId || !state.params) throw new Error('Incomplete wizard state')
      const body = buildConfigBody({
        configId: state.configId,
        runtimeId: state.runtimeId,
        modelId: state.modelId,
        params: state.params,
      })
      const { error } = await api.POST('/configs', { body })
      if (error) throw error
    },
    onSuccess: () => {
      toast.success('Config created')
      void navigate({ to: '/configs/$id', params: { id: state.configId } })
    },
    onError: (err) => {
      const apiErr = extractApiError(err)
      if (apiErr?.code === 'CONFIG_INVALID') {
        const details = apiErr.details as { errors?: string[] } | undefined
        const msg =
          details?.errors?.join('; ') ?? apiErr.message ?? 'Configuration validation failed'
        setInlineError(msg)
        return
      }
      setInlineError(apiErr?.message ?? String(err))
    },
  })

  useEffect(() => {
    save.mutate()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on mount
  }, [])

  if (save.isPending) {
    return (
      <div className="flex items-center gap-3 text-sm text-zinc-600">
        <span className="inline-block size-4 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-600" />
        Saving config…
      </div>
    )
  }

  if (save.isError || inlineError) {
    return (
      <div className="space-y-4 max-w-lg">
        <p className="text-sm text-red-600">{inlineError ?? 'Failed to save config.'}</p>
        <Button type="button" variant="outline" onClick={() => dispatch({ type: 'goToStep', step: 4 })}>
          Go back
        </Button>
      </div>
    )
  }

  return null
}
