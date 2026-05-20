import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
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
import { AddLocalModelDialog } from './AddLocalModelDialog'
import { PullModelDialog } from './PullModelDialog'

export function ModelsPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [pullOpen, setPullOpen] = useState(false)
  const [addOpen, setAddOpen] = useState(false)

  const models = useQuery({
    queryKey: ['models'],
    queryFn: async () => {
      const { data, error } = await api.GET('/models')
      if (error) throw new Error('Failed to load models')
      return (data ?? []) as Array<{ id: string; format?: string; metadata?: { display_name?: string } }>
    },
  })

  const uninstall = useMutation({
    mutationFn: async ({ id, purge }: { id: string; purge: boolean }) => {
      const { error } = await api.DELETE('/models/{model_id}', {
        params: { path: { model_id: id }, query: { purge } },
      })
      if (error) throw error
    },
    onSuccess: () => {
      toast.success('Model uninstalled')
      void qc.invalidateQueries({ queryKey: ['models'] })
    },
    onError: errorToToast,
  })

  if (models.isPending) return <Skeleton className="h-64 w-full" />
  if (models.isError) return <ErrorCard title="Failed to load models" message={String(models.error)} />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Models</h1>
        <div className="flex gap-2">
          <Button size="sm" onClick={() => setPullOpen(true)}>
            Pull from HF
          </Button>
          <Button size="sm" variant="outline" onClick={() => setAddOpen(true)}>
            Add local
          </Button>
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>ID</TableHead>
            <TableHead>Format</TableHead>
            <TableHead>Display name</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {models.data!.map((model) => (
            <TableRow key={model.id}>
              <TableCell
                className="font-mono cursor-pointer"
                onClick={() => navigate({ to: '/models/$id', params: { id: model.id } })}
              >
                {model.id}
              </TableCell>
              <TableCell
                className="cursor-pointer"
                onClick={() => navigate({ to: '/models/$id', params: { id: model.id } })}
              >
                {model.format ?? '—'}
              </TableCell>
              <TableCell
                className="cursor-pointer"
                onClick={() => navigate({ to: '/models/$id', params: { id: model.id } })}
              >
                {model.metadata?.display_name ?? '—'}
              </TableCell>
              <TableCell>
                <Button
                  size="xs"
                  variant="outline"
                  onClick={() => {
                    if (!window.confirm(`Uninstall model "${model.id}"?`)) return
                    const purge = window.confirm('Purge model files from disk?')
                    uninstall.mutate({ id: model.id, purge })
                  }}
                >
                  Uninstall
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <PullModelDialog open={pullOpen} onOpenChange={setPullOpen} />
      <AddLocalModelDialog open={addOpen} onOpenChange={setAddOpen} />
    </div>
  )
}
