import { useStartJob } from '@/hooks/useStartJob'
import type { UpdateCheckResult } from '@/hooks/useUpdateCheck'
import { Button } from '@/components/ui/button'

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  info: UpdateCheckResult
}

export function UpdateDialog({ open, onOpenChange, info }: Props) {
  const startJob = useStartJob()

  if (!open) return null

  const onUpdate = () => {
    startJob.mutate(
      { path: '/update', params: { query: { restart_dashboard: true } } },
      { onSuccess: () => onOpenChange(false) },
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md space-y-4">
        <h2 className="text-lg font-semibold">Update available</h2>
        <p className="text-sm text-zinc-600">
          Current version: <span className="font-mono">{info.current}</span>
          <br />
          Latest version: <span className="font-mono">{info.latest}</span>
        </p>
        {info.release_url ? (
          <p className="text-sm">
            <a
              href={info.release_url}
              target="_blank"
              rel="noreferrer"
              className="text-blue-600 underline"
            >
              Release notes
            </a>
          </p>
        ) : null}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="button" onClick={onUpdate} disabled={startJob.isPending}>
            {startJob.isPending ? 'Starting…' : 'Update now'}
          </Button>
        </div>
      </div>
    </div>
  )
}
