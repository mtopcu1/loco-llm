import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { JobRecord } from '@/hooks/useJobs'
import { useAppStore } from '@/store'
import { jobTitle, shortenUrl } from '@/lib/jobLabel'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

function contextSummary(context: Record<string, unknown> | undefined): string {
  if (!context) return ''
  const url = context.url
  if (typeof url === 'string') return shortenUrl(url, 48)
  return Object.entries(context)
    .map(([k, v]) => `${k}: ${String(v)}`)
    .join(', ')
}

function elapsed(startedAt: string | null | undefined): string {
  if (!startedAt) return ''
  const ms = Date.now() - new Date(startedAt).getTime()
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

type Props = {
  job: JobRecord
  compact?: boolean
  failed?: boolean
}

export function JobsTrayItem({ job, compact, failed }: Props) {
  const setSelectedJobId = useAppStore((s) => s.setSelectedJobId)
  const qc = useQueryClient()

  const cancel = useMutation({
    mutationFn: async () => {
      const { error } = await api.POST('/jobs/{job_id}/cancel', {
        params: { path: { job_id: job.id } },
      })
      if (error) throw error
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  return (
    <div
      className={cn(
        'flex items-center gap-2 rounded border px-2 py-1.5 text-xs cursor-pointer hover:bg-zinc-50',
        compact && 'py-1',
      )}
      onClick={() => setSelectedJobId(job.id)}
      onKeyDown={(e) => e.key === 'Enter' && setSelectedJobId(job.id)}
      role="button"
      tabIndex={0}
    >
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate">{jobTitle(job.kind, job.context)}</div>
        <div className="text-zinc-500 truncate">{contextSummary(job.context)}</div>
        {failed && job.error?.message ? (
          <div className="text-red-600 truncate">{job.error.message}</div>
        ) : (
          job.progress?.stage && (
            <div className="text-zinc-400 truncate">{job.progress.stage}</div>
          )
        )}
      </div>
      {!failed && (
        <>
          <span className="text-zinc-400 shrink-0">{elapsed(job.started_at)}</span>
          <Button
            size="xs"
            variant="ghost"
            className="shrink-0 h-6 px-1"
            disabled={cancel.isPending}
            onClick={(e) => {
              e.stopPropagation()
              cancel.mutate()
            }}
          >
            ×
          </Button>
        </>
      )}
      {failed && <span className="text-red-600 shrink-0 text-[10px] font-medium">failed</span>}
    </div>
  )
}
