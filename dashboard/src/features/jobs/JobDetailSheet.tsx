import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { useJob } from '@/hooks/useJob'
import { useSSE } from '@/hooks/useSSE'
import { useAppStore } from '@/store'
import { jobTitle, shortenUrl } from '@/lib/jobLabel'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'

function contextSummary(context: Record<string, unknown> | undefined): string {
  if (!context) return ''
  const url = context.url
  if (typeof url === 'string') return shortenUrl(url)
  const parts = Object.entries(context).map(([k, v]) => `${k}: ${String(v)}`)
  return parts.join(', ')
}

export function JobDetailSheet() {
  const jobId = useAppStore((s) => s.selectedJobId)
  const setSelectedJobId = useAppStore((s) => s.setSelectedJobId)
  const job = useJob(jobId)
  const qc = useQueryClient()
  const [logLines, setLogLines] = useState<string[]>([])
  const logEndRef = useRef<HTMLDivElement>(null)
  const notifiedStatus = useRef<string | null>(null)

  const logStream = useSSE<{ log?: string; status?: string }>({
    url: jobId ? `/api/jobs/${jobId}/stream` : '',
    enabled: !!jobId,
    eventNames: ['snapshot', 'update'],
  })

  useEffect(() => {
    if (!logStream.event?.log) return
    setLogLines((prev) => [...prev, logStream.event!.log!])
  }, [logStream.event])

  useEffect(() => {
    setLogLines([])
    notifiedStatus.current = null
  }, [jobId])

  useEffect(() => {
    const status = job.data?.status
    if (!status || status === notifiedStatus.current) return
    if (status !== 'succeeded' && status !== 'failed') return
    notifiedStatus.current = status
    if (status === 'succeeded' && job.data?.kind === 'model_pull') {
      void qc.invalidateQueries({ queryKey: ['models'] })
      toast.success('Model registered')
    }
    if (status === 'failed' && job.data?.error) {
      toast.error(job.data.error.message)
    }
  }, [job.data, qc])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logLines])

  const cancel = useMutation({
    mutationFn: async () => {
      const { error } = await api.POST('/jobs/{job_id}/cancel', {
        params: { path: { job_id: jobId! } },
      })
      if (error) throw error
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['jobs'] })
      if (jobId) void qc.invalidateQueries({ queryKey: ['jobs', jobId] })
    },
  })

  const j = job.data
  const open = !!jobId
  const title = jobTitle(j?.kind, j?.context)

  return (
    <Sheet open={open} onOpenChange={(o) => !o && setSelectedJobId(null)}>
      <SheetContent side="right" className="w-full sm:max-w-lg flex flex-col">
        <SheetHeader>
          <SheetTitle className="text-base">{title}</SheetTitle>
          <SheetDescription className="font-mono text-xs break-all">
            {jobId}
            {j?.status && (
              <Badge variant="secondary" className="ml-2 align-middle">
                {j.status}
              </Badge>
            )}
          </SheetDescription>
        </SheetHeader>

        {j && (
          <dl className="text-sm space-y-1 px-1">
            <div>
              <dt className="text-zinc-500 inline">Context: </dt>
              <dd className="inline break-all">{contextSummary(j.context)}</dd>
            </div>
            {j.progress?.stage && (
              <div>
                <dt className="text-zinc-500 inline">Stage: </dt>
                <dd className="inline">{j.progress.stage}</dd>
              </div>
            )}
            {j.error && (
              <p className="text-red-600 text-xs whitespace-pre-wrap">{j.error.message}</p>
            )}
          </dl>
        )}

        <pre className="flex-1 min-h-0 mt-4 text-xs font-mono bg-zinc-950 text-zinc-100 rounded p-3 overflow-y-auto max-h-[60vh]">
          {logLines.length === 0 ? (
            <span className="text-zinc-500">
              {j?.status === 'running' || j?.status === 'queued'
                ? 'Waiting for output from the CLI…'
                : 'No log output captured.'}
            </span>
          ) : (
            logLines.map((line, i) => (
              <div key={`${i}-${line.slice(0, 20)}`}>{line}</div>
            ))
          )}
          <div ref={logEndRef} />
        </pre>

        {j && (j.status === 'queued' || j.status === 'running') && (
          <Button
            variant="outline"
            size="sm"
            className="mt-2"
            disabled={cancel.isPending}
            onClick={() => cancel.mutate()}
          >
            Cancel job
          </Button>
        )}
      </SheetContent>
    </Sheet>
  )
}
