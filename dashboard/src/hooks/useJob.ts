import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import { useSSE } from '@/hooks/useSSE'
import type { JobRecord } from '@/hooks/useJobs'

type JobStreamEvent = Partial<JobRecord> & { log?: string }

export function useJob(id: string | null) {
  const qc = useQueryClient()
  const snapshot = useQuery({
    queryKey: ['jobs', id],
    queryFn: async () => {
      const { data, error } = await api.GET('/jobs/{job_id}', {
        params: { path: { job_id: id! } },
      })
      if (error) throw error
      return data as JobRecord
    },
    enabled: !!id,
  })

  const sse = useSSE<JobStreamEvent>({
    url: id ? `/api/jobs/${id}/stream` : '',
    enabled: !!id && !!snapshot.data,
    eventNames: ['snapshot', 'update'],
  })

  useEffect(() => {
    if (!id || !sse.event) return
    const ev = sse.event
    if (ev.log) return
    qc.setQueryData(['jobs', id], (prev: JobRecord | undefined) =>
      prev ? { ...prev, ...ev } : prev,
    )
    const status = ev.status
    if (status === 'succeeded' || status === 'failed' || status === 'cancelled') {
      void qc.invalidateQueries({ queryKey: ['jobs'] })
    }
  }, [sse.event, qc, id])

  return snapshot
}
