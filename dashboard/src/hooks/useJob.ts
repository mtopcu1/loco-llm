import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import { unwrapApi } from '@/api/helpers'
import { useSSE } from '@/hooks/useSSE'
import type { JobRecord } from '@/hooks/useJobs'

type JobStreamEvent = Partial<JobRecord> & { log?: string }

export function useJob(id: string | null) {
  const qc = useQueryClient()
  const [logLines, setLogLines] = useState<string[]>([])

  const snapshot = useQuery({
    queryKey: ['jobs', id],
    queryFn: async () => {
      const data = await unwrapApi(() =>
        api.GET('/jobs/{job_id}', {
          params: { path: { job_id: id! } },
        }),
      )
      return data as JobRecord
    },
    enabled: !!id,
  })

  const active =
    snapshot.data?.status === 'queued' || snapshot.data?.status === 'running'

  const sse = useSSE<JobStreamEvent>({
    url: id ? `/api/jobs/${id}/stream` : '',
    enabled: !!id && !!snapshot.data && active,
    eventNames: ['snapshot', 'update'],
  })

  useEffect(() => {
    if (!id) {
      setLogLines([])
      return
    }
    let cancelled = false
    void (async () => {
      try {
        const { data, error } = await api.GET('/jobs/{job_id}/log', {
          params: { path: { job_id: id } },
        })
        if (error) throw error
        const body = data as { lines?: string[] } | undefined
        if (!cancelled) setLogLines(body?.lines ?? [])
      } catch {
        if (!cancelled) setLogLines([])
      }
    })()
    return () => {
      cancelled = true
    }
  }, [id, snapshot.data?.status, snapshot.data?.finished_at])

  useEffect(() => {
    if (!id || !active) return
    setLogLines([])
  }, [id, active])

  useEffect(() => {
    if (!id || !sse.event) return
    const ev = sse.event
    if (ev.log) {
      setLogLines((prev) => [...prev, ev.log!])
      return
    }
    qc.setQueryData(['jobs', id], (prev: JobRecord | undefined) =>
      prev ? { ...prev, ...ev } : prev,
    )
    const status = ev.status
    if (status === 'succeeded' || status === 'failed' || status === 'cancelled') {
      void qc.invalidateQueries({ queryKey: ['jobs'] })
    }
  }, [sse.event, qc, id, active])

  return { ...snapshot, logLines, logStreamConnected: sse.connected }
}
