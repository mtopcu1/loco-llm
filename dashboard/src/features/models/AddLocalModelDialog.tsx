import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { errorToToast } from '@/lib/errorToToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const schema = z.object({
  id: z.string().min(1, 'ID is required'),
  path: z.string().min(1, 'Path is required'),
  format: z.string().min(1, 'Format is required'),
})

type FormValues = z.infer<typeof schema>

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function AddLocalModelDialog({ open, onOpenChange }: Props) {
  const qc = useQueryClient()
  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const add = useMutation({
    mutationFn: async (body: FormValues) => {
      const { error } = await api.POST('/models/add', { body })
      if (error) throw error
    },
    onSuccess: () => {
      toast.success('Model registered')
      void qc.invalidateQueries({ queryKey: ['models'] })
      onOpenChange(false)
      reset()
    },
    onError: errorToToast,
  })

  const onSubmit = handleSubmit((values) => add.mutate(values))

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <form
        className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md space-y-4"
        onSubmit={onSubmit}
      >
        <h2 className="text-lg font-semibold">Add local model</h2>
        <div>
          <label className="text-sm font-medium" htmlFor="local-id">
            ID
          </label>
          <Input id="local-id" {...register('id')} />
          {errors.id && <p className="text-red-600 text-xs mt-1">{errors.id.message}</p>}
        </div>
        <div>
          <label className="text-sm font-medium" htmlFor="local-path">
            Path
          </label>
          <Input id="local-path" {...register('path')} />
          {errors.path && <p className="text-red-600 text-xs mt-1">{errors.path.message}</p>}
        </div>
        <div>
          <label className="text-sm font-medium" htmlFor="local-format">
            Format
          </label>
          <Input id="local-format" {...register('format')} placeholder="gguf" />
          {errors.format && (
            <p className="text-red-600 text-xs mt-1">{errors.format.message}</p>
          )}
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" disabled={add.isPending}>
            Add
          </Button>
        </div>
      </form>
    </div>
  )
}
