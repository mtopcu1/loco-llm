import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { unwrapApi } from '@/api/helpers'
import { parseConfigDetail, type ParsedConfig } from '@/lib/configDocument'

export function useConfigDocument(configId: string, enabled = true) {
  return useQuery({
    queryKey: ['configs', configId],
    enabled: enabled && Boolean(configId),
    queryFn: async () => {
      const data = await unwrapApi(() =>
        api.GET('/configs/{config_id}', {
          params: { path: { config_id: configId } },
        }),
      )
      return parseConfigDetail(data)
    },
  })
}

export type { ParsedConfig }
