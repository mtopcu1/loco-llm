import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { errorToToast } from '@/lib/errorToToast'
import { ErrorCard } from '@/components/ErrorCard'
import { Button } from '@/components/ui/button'
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
  const qc = useQueryClient()
  const configs = useQuery({
    queryKey: ['configs'],
    queryFn: async () => {
      const { data, error } = await api.GET('/configs')
      if (error) throw new Error('Failed to load configs')
      return (data ?? []) as Array<{ id: string; source?: string }>
    },
  })

  const remove = useMutation({
    mutationFn: async (id: string) => {
      const { error } = await api.DELETE('/configs/{config_id}', {
        params: { path: { config_id: id } },
      })
      if (error) throw error
    },
    onSuccess: () => {
      toast.success('Config deleted')
      void qc.invalidateQueries({ queryKey: ['configs'] })
    },
    onError: errorToToast,
  })

  if (configs.isPending) return <Skeleton className="h-64 w-full" />
  if (configs.isError) return <ErrorCard title="Failed to load configs" message={String(configs.error)} />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Configs</h1>
        <Link to="/configs/new">
          <Button size="sm">New config</Button>
        </Link>
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
                <Button
                  size="xs"
                  variant="outline"
                  onClick={() => {
                    if (!window.confirm(`Delete config "${cfg.id}"?`)) return
                    remove.mutate(cfg.id)
                  }}
                >
                  Delete
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
