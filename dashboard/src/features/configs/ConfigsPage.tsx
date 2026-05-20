import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { api } from '@/api/client'
import { Plan2Button } from '@/components/Plan2Button'
import { ErrorCard } from '@/components/ErrorCard'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

export function ConfigsPage() {
  const navigate = useNavigate()
  const configs = useQuery({
    queryKey: ['configs'],
    queryFn: async () => {
      const { data, error } = await api.GET('/configs')
      if (error) throw new Error('Failed to load configs')
      return (data ?? []) as Array<{ id: string; source?: string }>
    },
  })

  if (configs.isPending) return <Skeleton className="h-64 w-full" />
  if (configs.isError) return <ErrorCard title="Failed to load configs" message={String(configs.error)} />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Configs</h1>
        <Plan2Button size="sm">New config</Plan2Button>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>ID</TableHead>
            <TableHead>Source</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {configs.data!.map((cfg) => (
            <TableRow
              key={cfg.id}
              className="cursor-pointer"
              onClick={() => navigate({ to: '/configs/$id', params: { id: cfg.id } })}
            >
              <TableCell className="font-mono">{cfg.id}</TableCell>
              <TableCell>{cfg.source ?? '—'}</TableCell>
              <TableCell onClick={(e) => e.stopPropagation()}>
                <Plan2Button size="xs" variant="outline">Delete</Plan2Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
