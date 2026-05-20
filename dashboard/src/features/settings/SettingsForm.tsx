import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { getApiError } from '@/lib/apiError'
import { errorToToast } from '@/lib/errorToToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card } from '@/components/ui/card'

type RegistryField = { key: string; kind?: string; label?: string }

type Props = {
  registry: RegistryField[]
  stored: Record<string, unknown>
}

export function SettingsForm({ registry, stored }: Props) {
  const qc = useQueryClient()
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({})

  const save = useMutation({
    mutationFn: async ({ key, value }: { key: string; value: string | null }) => {
      const { error } = await api.PUT('/settings/{key}', {
        params: { path: { key } },
        body: { value },
      })
      if (error) throw error
    },
    onSuccess: () => {
      toast.success('Setting saved')
      void qc.invalidateQueries({ queryKey: ['settings'] })
      setRowErrors({})
    },
    onError: (err, { key }) => {
      errorToToast(err)
      const body = getApiError(err)
      setRowErrors((prev) => ({
        ...prev,
        [key]: body?.message ?? String(err),
      }))
    },
  })

  return (
    <Card className="p-4">
      <h2 className="font-medium mb-3">Edit settings</h2>
      <ul className="space-y-4">
        {registry.map((field) => {
          const current = drafts[field.key] ?? String(stored[field.key] ?? '')
          return (
            <li key={field.key} className="border-b pb-4 last:border-0">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <span className="font-mono text-sm">{field.key}</span>
                  {field.label && (
                    <span className="text-zinc-500 ml-2 text-sm">({field.label})</span>
                  )}
                  {field.kind && (
                    <span className="text-zinc-400 ml-2 text-xs">{field.kind}</span>
                  )}
                </div>
                <div className="flex gap-2 items-center flex-1 max-w-md">
                  <Input
                    value={current}
                    onChange={(e) =>
                      setDrafts((d) => ({ ...d, [field.key]: e.target.value }))
                    }
                    className="font-mono text-sm"
                  />
                  <Button
                    size="sm"
                    disabled={save.isPending}
                    onClick={() => save.mutate({ key: field.key, value: current })}
                  >
                    Save
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={save.isPending}
                    onClick={() => save.mutate({ key: field.key, value: null })}
                  >
                    Reset
                  </Button>
                </div>
              </div>
              {rowErrors[field.key] && (
                <p className="text-red-600 text-xs mt-1">{rowErrors[field.key]}</p>
              )}
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
