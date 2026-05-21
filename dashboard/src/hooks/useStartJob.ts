import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { apiPost } from '@/api/helpers'
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
      const data = (await apiPost(path, {
        params: params as { path?: Record<string, string>; query?: Record<string, string> },
        body,
      })) as { job_id?: string }
      return data
    },
    onSuccess: (data, variables) => {
      if (data?.job_id) {
        setSelectedJobId(data.job_id)
        void qc.invalidateQueries({ queryKey: ['jobs'] })
        if (
          variables.path === '/instance/start' ||
          variables.path === '/instance/switch' ||
          variables.path === '/instance/stop'
        ) {
          void qc.invalidateQueries({ queryKey: ['instance'] })
        }
        const startMsg =
          variables.path === '/instance/switch'
            ? 'Switching instance — open Jobs for live log'
            : variables.path === '/instance/start'
              ? 'Starting instance — open Jobs for live log'
              : 'Job started'
        toast.success(startMsg)
      }
    },
    onError: errorToToast,
  })
}
