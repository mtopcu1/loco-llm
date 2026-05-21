import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { errorToToast } from '@/lib/errorToToast'
import { useStartJob } from '@/hooks/useStartJob'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

type InstanceState = {
  running: boolean
  config_id?: string
  mode?: string
}

export function InstanceControls() {
  const qc = useQueryClient()
  const startJob = useStartJob()
  const [configId, setConfigId] = useState('')
  const [switchId, setSwitchId] = useState('')
  const [mode, setMode] = useState<'background' | 'systemd'>('background')

  const instance = useQuery({
    queryKey: ['instance'],
    queryFn: async () => {
      const { data, error } = await api.GET('/instance')
      if (error) throw new Error('Failed to load instance')
      return data as InstanceState
    },
  })

  const configs = useQuery({
    queryKey: ['configs'],
    queryFn: async () => {
      const { data, error } = await api.GET('/configs')
      if (error) throw new Error('Failed to load configs')
      return (data ?? []) as Array<{ id: string }>
    },
    refetchOnMount: 'always',
  })

  useEffect(() => {
    void qc.invalidateQueries({ queryKey: ['configs'] })
    void qc.invalidateQueries({ queryKey: ['instance'] })
  }, [qc])

  const stop = useMutation({
    mutationFn: async () => {
      const { error } = await api.POST('/instance/stop')
      if (error) throw error
    },
    onSuccess: () => {
      toast.success('Instance stopped')
      void qc.invalidateQueries({ queryKey: ['instance'] })
    },
    onError: errorToToast,
  })

  const state = instance.data
  if (!state) return null

  const isForeground = state.running && state.mode === 'foreground'

  if (!state.running) {
    return (
      <Card className="p-6 space-y-4">
        <p className="text-zinc-600 text-sm">Start a config in the background or via systemd.</p>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label className="text-sm font-medium" htmlFor="start-config">
              Config
            </label>
            <select
              id="start-config"
              className="w-full border rounded-md px-2 py-1.5 text-sm mt-1"
              value={configId}
              onChange={(e) => setConfigId(e.target.value)}
            >
              <option value="">Select config…</option>
              {(configs.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.id}
                </option>
              ))}
            </select>
          </div>
          <fieldset className="text-sm">
            <legend className="font-medium mb-1">Mode</legend>
            <label className="mr-3">
              <input
                type="radio"
                checked={mode === 'background'}
                onChange={() => setMode('background')}
              />{' '}
              background
            </label>
            <label>
              <input
                type="radio"
                checked={mode === 'systemd'}
                onChange={() => setMode('systemd')}
              />{' '}
              systemd
            </label>
          </fieldset>
          <Button
            disabled={!configId || startJob.isPending}
            onClick={() =>
              startJob.mutate({
                path: '/instance/start',
                body: { config_id: configId, mode },
              })
            }
          >
            Start
          </Button>
        </div>
      </Card>
    )
  }

  return (
    <Card className="p-6 space-y-4">
      <p className="text-sm">
        Running <span className="font-mono">{state.config_id}</span> ({state.mode ?? '—'})
      </p>
      <div className="flex flex-wrap gap-2 items-end">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span>
                <Button
                  variant="destructive"
                  disabled={isForeground || stop.isPending}
                  onClick={() => stop.mutate()}
                >
                  Stop
                </Button>
              </span>
            </TooltipTrigger>
            {isForeground && (
              <TooltipContent>
                Started in foreground from terminal — use Ctrl-C in that terminal to stop.
              </TooltipContent>
            )}
          </Tooltip>
        </TooltipProvider>
        <select
          className="border rounded-md px-2 py-1.5 text-sm"
          value={switchId}
          onChange={(e) => setSwitchId(e.target.value)}
        >
          <option value="">Switch to…</option>
          {(configs.data ?? [])
            .filter((c) => c.id !== state.config_id)
            .map((c) => (
              <option key={c.id} value={c.id}>
                {c.id}
              </option>
            ))}
        </select>
        <Button
          variant="outline"
          disabled={!switchId || isForeground || startJob.isPending}
          onClick={() =>
            startJob.mutate({
              path: '/instance/switch',
              body: { config_id: switchId },
            })
          }
        >
          Switch
        </Button>
      </div>
    </Card>
  )
}
