import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { errorToToast } from '@/lib/errorToToast'
import { useStartJob } from '@/hooks/useStartJob'
import { Button } from '@/components/ui/button'

type Props = {
  runtimeId: string
  installed: boolean
  size?: 'default' | 'xs' | 'sm'
}

export function RuntimeActions({ runtimeId, installed, size = 'xs' }: Props) {
  const qc = useQueryClient()
  const startJob = useStartJob()

  const uninstall = useMutation({
    mutationFn: async (purge: boolean) => {
      const { error } = await api.DELETE('/runtimes/{runtime_id}', {
        params: { path: { runtime_id: runtimeId }, query: { purge } },
      })
      if (error) throw error
    },
    onSuccess: () => {
      toast.success('Runtime uninstalled')
      void qc.invalidateQueries({ queryKey: ['runtimes'] })
      void qc.invalidateQueries({ queryKey: ['runtimes', runtimeId] })
    },
    onError: errorToToast,
  })

  const onUninstall = () => {
    if (!window.confirm(`Uninstall runtime "${runtimeId}"?`)) return
    const purge = window.confirm('Also purge runtime data from disk?')
    uninstall.mutate(purge)
  }

  return (
    <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
      {!installed && (
        <Button
          size={size}
          variant="outline"
          disabled={startJob.isPending}
          onClick={() =>
            startJob.mutate({
              path: '/runtimes/{runtime_id}/install',
              params: { runtime_id: runtimeId },
            })
          }
        >
          Install
        </Button>
      )}
      {installed && (
        <>
          <Button
            size={size}
            variant="outline"
            disabled={startJob.isPending}
            onClick={() =>
              startJob.mutate({
                path: '/runtimes/{runtime_id}/rebuild',
                params: { runtime_id: runtimeId },
              })
            }
          >
            Rebuild
          </Button>
          <Button
            size={size}
            variant="outline"
            disabled={uninstall.isPending}
            onClick={onUninstall}
          >
            Uninstall
          </Button>
        </>
      )}
    </div>
  )
}
