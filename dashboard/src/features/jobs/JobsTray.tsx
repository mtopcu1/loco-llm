import { useJobs } from '@/hooks/useJobs'
import { useAppStore } from '@/store'
import { JobsTrayItem } from './JobsTrayItem'
import { cn } from '@/lib/utils'

const ACTIVE = new Set(['queued', 'running'])

export function JobsTray() {
  const collapsed = useAppStore((s) => s.sidebarCollapsed)
  const trayOpen = useAppStore((s) => s.jobsTrayOpen)
  const setTrayOpen = useAppStore((s) => s.setJobsTrayOpen)
  const jobs = useJobs()

  const active = (jobs.data ?? []).filter((j) => ACTIVE.has(j.status))

  if (collapsed) return null

  return (
    <div className="mt-auto border-t p-2">
      <button
        type="button"
        className="w-full text-left text-xs font-medium text-zinc-600 hover:text-zinc-900 flex items-center justify-between"
        onClick={() => setTrayOpen(!trayOpen)}
      >
        <span>Jobs{active.length > 0 ? ` (${active.length})` : ''}</span>
        <span>{trayOpen ? '▼' : '▶'}</span>
      </button>
      <div className={cn('space-y-1 mt-1', !trayOpen && 'hidden')}>
        {jobs.isLoading && <p className="text-xs text-zinc-400">Loading…</p>}
        {active.length === 0 && !jobs.isLoading && (
          <p className="text-xs text-zinc-400">No active jobs</p>
        )}
        {active.map((job) => (
          <JobsTrayItem key={job.id} job={job} />
        ))}
      </div>
    </div>
  )
}
