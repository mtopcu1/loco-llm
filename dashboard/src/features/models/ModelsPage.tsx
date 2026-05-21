import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useJobs, type JobRecord } from '@/hooks/useJobs'
import { jobTitle } from '@/lib/jobLabel'
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

const ACTIVE_JOB = new Set(['queued', 'running'])

function pendingModelPulls(jobs: JobRecord[] | undefined): JobRecord[] {
  return (jobs ?? []).filter((j) => j.kind === 'model_pull' && ACTIVE_JOB.has(j.status))
}

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

  const jobs = useJobs()
  const inProgressPulls = pendingModelPulls(jobs.data)

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
          {inProgressPulls.map((job) => (
            <TableRow key={job.id} className="bg-zinc-50/80">
              <TableCell className="font-mono text-zinc-500 italic" colSpan={2}>
                {jobTitle(job.kind, job.context)}
              </TableCell>
              <TableCell className="text-zinc-600 text-sm">
                {job.progress?.stage ?? job.status}
                {job.progress?.percent != null ? ` (${job.progress.percent}%)` : ''}
              </TableCell>
              <TableCell className="text-zinc-500 text-xs">Pulling…</TableCell>
            </TableRow>
          ))}
          {models.data!.length === 0 && inProgressPulls.length === 0 && (
            <TableRow>
              <TableCell colSpan={4} className="text-zinc-500 text-sm py-8 text-center">
                No models yet. Use <strong>Pull from HF</strong> with a file URL (…/blob/main/….gguf)
                or <strong>Add local</strong> for weights already on disk.
              </TableCell>
            </TableRow>
          )}
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
