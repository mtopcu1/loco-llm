import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { api } from '@/api/client'
import { Plan2Button } from '@/components/Plan2Button'
import { ErrorCard } from '@/components/ErrorCard'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

export function RuntimesPage() {
  const navigate = useNavigate()
  const runtimes = useQuery({
    queryKey: ['runtimes'],
    queryFn: async () => {
      const { data, error } = await api.GET('/runtimes')
      if (error) throw new Error('Failed to load runtimes')
      return data ?? []
    },
  })

  if (runtimes.isPending) return <Skeleton className="h-64 w-full" />
  if (runtimes.isError) return <ErrorCard title="Failed to load runtimes" message={String(runtimes.error)} />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Runtimes</h1>
        <Plan2Button size="sm">Install runtime</Plan2Button>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>ID</TableHead>
            <TableHead>Kind</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {runtimes.data!.map((rt) => (
            <TableRow
              key={rt.id}
              className="cursor-pointer"
              onClick={() => navigate({ to: '/runtimes/$id', params: { id: rt.id } })}
            >
              <TableCell className="font-mono">{rt.id}</TableCell>
              <TableCell>{rt.kind}</TableCell>
              <TableCell>
                {rt.installed ? (
                  <Badge variant="default">installed</Badge>
                ) : (
                  <Badge variant="secondary">not installed</Badge>
                )}
              </TableCell>
              <TableCell onClick={(e) => e.stopPropagation()}>
                <div className="flex gap-2">
                  <Plan2Button size="xs" variant="outline">Install</Plan2Button>
                  <Plan2Button size="xs" variant="outline">Rebuild</Plan2Button>
                  <Plan2Button size="xs" variant="outline">Uninstall</Plan2Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
