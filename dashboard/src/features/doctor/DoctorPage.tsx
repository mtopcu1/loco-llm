import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { ErrorCard } from '@/components/ErrorCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

type CheckResult = { name: string; status: string; message: string }

function statusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status === 'ok') return 'default'
  if (status === 'warning') return 'secondary'
  return 'destructive'
}

function CheckList({ checks }: { checks: CheckResult[] }) {
  const [expanded, setExpanded] = useState<string | null>(null)

  return (
    <ul className="space-y-3">
      {checks.map((check) => (
        <li key={check.name} className="rounded border p-3">
          <div className="flex items-center gap-3">
            <Badge variant={statusVariant(check.status)}>{check.status}</Badge>
            <span className="font-mono text-sm">{check.name}</span>
          </div>
          <p className="mt-2 text-sm text-zinc-600">{check.message}</p>
          {check.message.length > 60 && (
            <button
              type="button"
              className="mt-1 text-xs text-zinc-500 underline"
              onClick={() => setExpanded(expanded === check.name ? null : check.name)}
            >
              {expanded === check.name ? 'Hide details' : 'Show details'}
            </button>
          )}
        </li>
      ))}
    </ul>
  )
}

export function DoctorPage() {
  const doctor = useQuery({
    queryKey: ['doctor'],
    queryFn: async () => {
      const { data, error } = await api.GET('/doctor')
      if (error) throw new Error('Failed to load doctor results')
      return data as { scopes: Record<string, CheckResult[]> }
    },
  })

  if (doctor.isPending) return <Skeleton className="h-64 w-full" />
  if (doctor.isError) return <ErrorCard title="Failed to load doctor" message={String(doctor.error)} />

  const scopes = doctor.data!.scopes

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Doctor</h1>
        <Button variant="outline" onClick={() => doctor.refetch()} disabled={doctor.isFetching}>
          {doctor.isFetching ? 'Re-running…' : 'Re-run'}
        </Button>
      </div>

      <Tabs defaultValue="default">
        <TabsList>
          {Object.keys(scopes).map((scope) => (
            <TabsTrigger key={scope} value={scope}>
              {scope}
            </TabsTrigger>
          ))}
        </TabsList>
        {Object.entries(scopes).map(([scope, checks]) => (
          <TabsContent key={scope} value={scope}>
            <CheckList checks={checks} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}
