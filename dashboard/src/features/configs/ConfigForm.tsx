import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { errorToToast } from '@/lib/errorToToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const schema = z.object({
  id: z.string().min(1, 'ID is required'),
  runtime: z.string().min(1, 'Runtime is required'),
  model: z.string().optional(),
  paramsJson: z.string().refine((s) => {
    try {
      JSON.parse(s)
      return true
    } catch {
      return false
    }
  }, 'Params must be valid JSON'),
})

type FormValues = z.infer<typeof schema>

type Props = {
  mode: 'create' | 'update'
  initial?: {
    id: string
    runtime: string
    model?: string
    serve?: { params?: Record<string, unknown> }
  }
  onCancel?: () => void
}

function toBody(values: FormValues) {
  const params = JSON.parse(values.paramsJson) as Record<string, unknown>
  return {
    id: values.id,
    runtime: values.runtime,
    model: values.model || undefined,
    serve: { host: '127.0.0.1', port: 8000, params },
    readiness: { timeout_seconds: 600 },
  }
}

export function ConfigForm({ mode, initial, onCancel }: Props) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      id: initial?.id ?? '',
      runtime: initial?.runtime ?? '',
      model: initial?.model ?? '',
      paramsJson: JSON.stringify(initial?.serve?.params ?? {}, null, 2),
    },
  })

  const save = useMutation({
    mutationFn: async (values: FormValues) => {
      const body = toBody(values)
      if (mode === 'create') {
        const { error } = await api.POST('/configs', { body })
        if (error) throw error
      } else {
        const { error } = await api.PUT('/configs/{config_id}', {
          params: { path: { config_id: values.id } },
          body,
        })
        if (error) throw error
      }
    },
    onSuccess: (_data, values) => {
      toast.success(mode === 'create' ? 'Config created' : 'Config updated')
      void qc.invalidateQueries({ queryKey: ['configs'] })
      void qc.invalidateQueries({ queryKey: ['configs', values.id] })
      if (mode === 'create') {
        void navigate({ to: '/configs/$id', params: { id: values.id } })
      } else {
        onCancel?.()
      }
    },
    onError: errorToToast,
  })

  return (
    <form className="space-y-4" onSubmit={handleSubmit((v) => save.mutate(v))}>
      <div>
        <label className="text-sm font-medium" htmlFor="cfg-id">
          ID
        </label>
        <Input id="cfg-id" {...register('id')} disabled={mode === 'update'} />
        {errors.id && <p className="text-red-600 text-xs mt-1">{errors.id.message}</p>}
      </div>
      <div>
        <label className="text-sm font-medium" htmlFor="cfg-runtime">
          Runtime
        </label>
        <Input id="cfg-runtime" {...register('runtime')} />
        {errors.runtime && (
          <p className="text-red-600 text-xs mt-1">{errors.runtime.message}</p>
        )}
      </div>
      <div>
        <label className="text-sm font-medium" htmlFor="cfg-model">
          Model (optional)
        </label>
        <Input id="cfg-model" {...register('model')} />
      </div>
      <div>
        <label className="text-sm font-medium" htmlFor="cfg-params">
          Serve params (JSON)
        </label>
        <textarea
          id="cfg-params"
          className="w-full min-h-[120px] font-mono text-sm border rounded-md p-2"
          {...register('paramsJson')}
        />
        {errors.paramsJson && (
          <p className="text-red-600 text-xs mt-1">{errors.paramsJson.message}</p>
        )}
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={save.isPending}>
          {mode === 'create' ? 'Create' : 'Save'}
        </Button>
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  )
}
