import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useStartJob } from '@/hooks/useStartJob'
import { errorToToast } from '@/lib/errorToToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAppStore } from '@/store'

const schema = z.object({
  url: z.string().min(1, 'URL is required'),
  id: z.string().optional(),
  format: z.string().optional(),
  force: z.boolean().optional(),
})

type FormValues = z.infer<typeof schema>

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function PullModelDialog({ open, onOpenChange }: Props) {
  const startJob = useStartJob()
  const setJobsTrayOpen = useAppStore((s) => s.setJobsTrayOpen)
  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const onSubmit = handleSubmit((values) => {
    startJob.mutate(
      {
        path: '/models/pull',
        body: {
          url: values.url.trim(),
          id: values.id?.trim() || undefined,
          format: values.format?.trim() || undefined,
          force: values.force ?? false,
        },
      },
      {
        onSuccess: () => {
          setJobsTrayOpen(true)
          onOpenChange(false)
          reset()
        },
        onError: errorToToast,
      },
    )
  })

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <form
        className="bg-white rounded-lg shadow-lg p-6 w-full max-w-xl space-y-4"
        onSubmit={onSubmit}
      >
        <h2 className="text-lg font-semibold">Pull model from Hugging Face</h2>
        <p className="text-sm text-zinc-600">
          Paste a Hugging Face file URL (…/blob/main/….gguf) or repo URL. Progress appears in the
          job panel.
        </p>
        <div>
          <label className="text-sm font-medium" htmlFor="pull-url">
            URL
          </label>
          <textarea
            id="pull-url"
            rows={3}
            className="mt-1 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm font-mono shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
            placeholder="https://huggingface.co/org/repo/blob/main/model.gguf"
            {...register('url')}
          />
          {errors.url && <p className="text-red-600 text-xs mt-1">{errors.url.message}</p>}
        </div>
        <div>
          <label className="text-sm font-medium" htmlFor="pull-id">
            ID (optional)
          </label>
          <Input id="pull-id" {...register('id')} />
        </div>
        <div>
          <label className="text-sm font-medium" htmlFor="pull-format">
            Format (optional)
          </label>
          <Input id="pull-format" {...register('format')} placeholder="gguf" />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...register('force')} />
          Force re-download
        </label>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" disabled={startJob.isPending}>
            Pull
          </Button>
        </div>
      </form>
    </div>
  )
}
