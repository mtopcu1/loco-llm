import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { UpdateBadge } from './UpdateBadge'
import { StatusPill, type InstanceStatus } from './StatusPill'

export function Header() {
  const version = useQuery({
    queryKey: ['version'],
    queryFn: async () => {
      const { data } = await api.GET('/version')
      return data as { cli_version?: string } | undefined
    },
  })

  const instance = useQuery({
    queryKey: ['instance'],
    queryFn: async () => {
      const { data } = await api.GET('/instance')
      return data as InstanceStatus | undefined
    },
    refetchInterval: 5_000,
  })

  return (
    <header className="border-b bg-white px-6 py-3 flex items-center gap-4">
      <span className="font-semibold text-lg">LocalLLM</span>
      <span className="text-xs text-zinc-500">
        v{version.data?.cli_version ?? '…'}
      </span>
      <UpdateBadge />
      <div className="flex-1" />
      <StatusPill instance={instance.data} />
    </header>
  )
}
