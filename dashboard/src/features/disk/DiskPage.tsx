import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { Plan2Button } from '@/components/Plan2Button'
import { ErrorCard } from '@/components/ErrorCard'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatBytes } from '@/lib/format'

type DiskData = {
  data_root: string
  data_root_bytes_total: number
  data_root_bytes_used: number
  data_root_bytes_free: number
  cache_bytes: number
  models: Array<{ id: string; bytes: number }>
}

export function DiskPage() {
  const disk = useQuery({
    queryKey: ['disk'],
    queryFn: async () => {
      const { data, error } = await api.GET('/disk')
      if (error) throw new Error('Failed to load disk usage')
      return data as DiskData
    },
    staleTime: 30_000,
  })

  if (disk.isPending) return <Skeleton className="h-64 w-full" />
  if (disk.isError) return <ErrorCard title="Failed to load disk" message={String(disk.error)} />

  const d = disk.data!
  const pctUsed = d.data_root_bytes_total
    ? Math.round((d.data_root_bytes_used / d.data_root_bytes_total) * 100)
    : 0

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold">Disk</h1>

      <Card className="p-4 space-y-3">
        <h2 className="font-medium">Data root</h2>
        <p className="text-sm text-zinc-500 font-mono">{d.data_root}</p>
        <dl className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <dt className="text-zinc-500">Total</dt>
            <dd>{formatBytes(d.data_root_bytes_total)}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Used</dt>
            <dd>{formatBytes(d.data_root_bytes_used)}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Free</dt>
            <dd>{formatBytes(d.data_root_bytes_free)}</dd>
          </div>
        </dl>
        <div className="space-y-1">
          <div className="flex justify-between text-sm">
            <span>{pctUsed}% used</span>
          </div>
          <div className="h-2 rounded-full bg-zinc-200 overflow-hidden">
            <div className="h-full bg-blue-500" style={{ width: `${pctUsed}%` }} />
          </div>
        </div>
      </Card>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-medium">Models</h2>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Size</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {d.models.map((model) => (
              <TableRow key={model.id}>
                <TableCell className="font-mono">{model.id}</TableCell>
                <TableCell>{formatBytes(model.bytes)}</TableCell>
                <TableCell>
                  <Plan2Button size="xs" variant="outline">Uninstall</Plan2Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </section>

      <Card className="p-4 flex items-center justify-between">
        <div>
          <h2 className="font-medium">Cache</h2>
          <p className="text-sm text-zinc-500">{formatBytes(d.cache_bytes)}</p>
        </div>
        <Plan2Button size="sm" variant="outline">Clear</Plan2Button>
      </Card>
    </div>
  )
}
