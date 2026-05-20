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

export function ModelsPage() {
  const navigate = useNavigate()
  const models = useQuery({
    queryKey: ['models'],
    queryFn: async () => {
      const { data, error } = await api.GET('/models')
      if (error) throw new Error('Failed to load models')
      return (data ?? []) as Array<{ id: string; format?: string; metadata?: { display_name?: string } }>
    },
  })

  if (models.isPending) return <Skeleton className="h-64 w-full" />
  if (models.isError) return <ErrorCard title="Failed to load models" message={String(models.error)} />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Models</h1>
        <div className="flex gap-2">
          <Plan2Button size="sm">Pull from HF</Plan2Button>
          <Plan2Button size="sm" variant="outline">Add local</Plan2Button>
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>ID</TableHead>
            <TableHead>Format</TableHead>
            <TableHead>Display name</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {models.data!.map((model) => (
            <TableRow
              key={model.id}
              className="cursor-pointer"
              onClick={() => navigate({ to: '/models/$id', params: { id: model.id } })}
            >
              <TableCell className="font-mono">{model.id}</TableCell>
              <TableCell>{model.format ?? '—'}</TableCell>
              <TableCell>{model.metadata?.display_name ?? '—'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
