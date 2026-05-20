import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import { ErrorCard } from '@/components/ErrorCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useSSE } from '@/hooks/useSSE'

const PAGE_SIZE = 25

type HistoryEntry = Record<string, unknown>

type HistoryFilters = {
  action: string
  config_id: string
  since: string
  until: string
}

export function HistoryPage() {
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState<HistoryFilters>({
    action: '',
    config_id: '',
    since: '',
    until: '',
  })
  const [limit, setLimit] = useState(PAGE_SIZE)

  const queryKey = useMemo(
    () => ['history', filters, limit] as const,
    [filters, limit],
  )

  const history = useQuery({
    queryKey,
    queryFn: async () => {
      const { data, error } = await api.GET('/history', {
        params: {
          query: {
            limit,
            offset: 0,
            action: filters.action || undefined,
            config_id: filters.config_id || undefined,
            since: filters.since || undefined,
            until: filters.until || undefined,
          },
        },
      })
      if (error) throw new Error('Failed to load history')
      return data as { items: HistoryEntry[]; total: number }
    },
  })

  const stream = useSSE<HistoryEntry>({
    url: '/api/history/stream',
    enabled: true,
  })

  useEffect(() => {
    if (!stream.event) return
    queryClient.setQueryData(queryKey, (prev: { items: HistoryEntry[]; total: number } | undefined) => {
      if (!prev) return prev
      const exists = prev.items.some(
        (item) => item.ts === stream.event!.ts && item.action === stream.event!.action,
      )
      if (exists) return prev
      return { items: [stream.event!, ...prev.items], total: prev.total + 1 }
    })
  }, [stream.event, queryClient, queryKey])

  if (history.isPending) return <Skeleton className="h-64 w-full" />
  if (history.isError) return <ErrorCard title="Failed to load history" message={String(history.error)} />

  const { items, total } = history.data!

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">History</h1>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <Input
          placeholder="Action"
          value={filters.action}
          onChange={(e) => setFilters((f) => ({ ...f, action: e.target.value }))}
        />
        <Input
          placeholder="Config ID"
          value={filters.config_id}
          onChange={(e) => setFilters((f) => ({ ...f, config_id: e.target.value }))}
        />
        <Input
          type="date"
          value={filters.since}
          onChange={(e) => setFilters((f) => ({ ...f, since: e.target.value }))}
        />
        <Input
          type="date"
          value={filters.until}
          onChange={(e) => setFilters((f) => ({ ...f, until: e.target.value }))}
        />
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Timestamp</TableHead>
            <TableHead>Action</TableHead>
            <TableHead>Config</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((entry, i) => (
            <TableRow key={`${String(entry.ts)}-${String(entry.action)}-${i}`}>
              <TableCell className="font-mono text-xs">{String(entry.ts ?? '—')}</TableCell>
              <TableCell>{String(entry.action ?? '—')}</TableCell>
              <TableCell className="font-mono">{String(entry.config_id ?? entry.id ?? '—')}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {items.length < total && (
        <Button variant="outline" onClick={() => setLimit((l) => l + PAGE_SIZE)}>
          Load more ({items.length} of {total})
        </Button>
      )}
    </div>
  )
}
