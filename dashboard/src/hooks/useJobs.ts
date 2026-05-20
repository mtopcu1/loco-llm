import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'

export type JobRecord = {
  id: string
  kind: string
  status: string
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  progress?: { percent?: number | null; stage?: string } | null
  error?: { code: string; message: string; details?: Record<string, unknown> } | null
  context?: Record<string, unknown>
}

export function useJobs() {
  return useQuery({
    queryKey: ['jobs'],
    queryFn: async () => {
      const { data, error } = await api.GET('/jobs')
      if (error) throw error
      return (data ?? []) as JobRecord[]
    },
    refetchInterval: 2000,
  })
}
