import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { errorToToast } from '@/lib/errorToToast'
import type { paths } from '@/api/generated'
import { useAppStore } from '@/store'

type PostPaths = {
  [K in keyof paths]: paths[K] extends { post: unknown } ? K : never
}[keyof paths]

type StartJobInput = {
  path: PostPaths
  params?: Record<string, string>
  body?: Record<string, unknown>
}

export function useStartJob() {
  const qc = useQueryClient()
  const setSelectedJobId = useAppStore((s) => s.setSelectedJobId)

  return useMutation({
    mutationFn: async ({ path, params, body }: StartJobInput) => {
      const { data, error } = await api.POST(path, {
        params: params as never,
        body: body as never,
      })
      if (error) throw error
      return data as { job_id?: string }
    },
    onSuccess: (data) => {
      if (data?.job_id) {
        setSelectedJobId(data.job_id)
        void qc.invalidateQueries({ queryKey: ['jobs'] })
        toast.success('Job started')
      }
    },
    onError: errorToToast,
  })
}
