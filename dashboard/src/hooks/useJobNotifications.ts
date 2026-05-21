import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useJobs, type JobRecord } from '@/hooks/useJobs'

function notifyTerminal(job: JobRecord, qc: ReturnType<typeof useQueryClient>) {
  const cfg = job.context?.config_id
  const cfgLabel = typeof cfg === 'string' && cfg ? cfg : undefined

  if (job.status === 'succeeded' && job.kind === 'instance_start_wait') {
    void qc.invalidateQueries({ queryKey: ['instance'] })
    toast.success(cfgLabel ? `Instance ready (${cfgLabel})` : 'Instance ready')
    return
  }

  if (job.status === 'failed' && job.kind === 'instance_start_wait' && job.error) {
    void qc.invalidateQueries({ queryKey: ['instance'] })
    const action = job.context?.action === 'switch' ? 'Switch failed' : 'Start failed'
    const detail = job.error.message
    toast.error(
      cfgLabel ? `${action}: ${cfgLabel} — ${detail}` : `${action}: ${detail}`,
      { duration: 12_000 },
    )
    return
  }

  if (job.status === 'succeeded' && job.kind === 'model_pull') {
    void qc.invalidateQueries({ queryKey: ['models'] })
    toast.success('Model registered')
  }
}

/** Toast when tracked jobs reach a terminal state (works even if the job sheet is closed). */
export function useJobNotifications() {
  const jobs = useJobs()
  const qc = useQueryClient()
  const seen = useRef(new Set<string>())

  useEffect(() => {
    for (const job of jobs.data ?? []) {
      if (job.status !== 'succeeded' && job.status !== 'failed') continue
      const key = `${job.id}:${job.status}`
      if (seen.current.has(key)) continue
      seen.current.add(key)
      if (job.kind === 'instance_start_wait' || job.kind === 'model_pull') {
        notifyTerminal(job, qc)
      }
    }
  }, [jobs.data, qc])
}
