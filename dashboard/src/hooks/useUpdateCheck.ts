import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'

export type UpdateCheckResult = {
  current: string
  latest: string
  update_available: boolean
  release_url: string | null
}

export function useUpdateCheck() {
  return useQuery({
    queryKey: ['update', 'check'],
    queryFn: async () => {
      const { data, error } = await api.GET('/update/check')
      if (error) throw error
      return data as UpdateCheckResult
    },
    staleTime: 6 * 60 * 60 * 1000,
    refetchInterval: 6 * 60 * 60 * 1000,
  })
}
