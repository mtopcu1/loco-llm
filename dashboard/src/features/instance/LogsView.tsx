import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { useSSE } from '@/hooks/useSSE'

const MAX_LINES = 5000

export function LogsView({ enabled }: { enabled: boolean }) {
  const [paused, setPaused] = useState(false)
  const bufferRef = useRef<string[]>([])
  const [, tick] = useState(0)

  const { event, connected } = useSSE<{ line?: string; error?: string }>({
    url: '/api/instance/logs/stream',
    enabled: enabled && !paused,
    parser: (raw) => JSON.parse(raw) as { line?: string; error?: string },
  })

  useEffect(() => {
    if (!event?.line) return
    const lines = bufferRef.current
    lines.push(event.line)
    if (lines.length > MAX_LINES) {
      bufferRef.current = lines.slice(-MAX_LINES)
    }
    tick((n) => n + 1)
  }, [event])

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm text-zinc-500">
        <span>{connected ? 'Connected' : 'Disconnected'}</span>
        <Button size="xs" variant="outline" onClick={() => setPaused((p) => !p)}>
          {paused ? 'Resume' : 'Pause'}
        </Button>
      </div>
      <pre className="text-xs bg-zinc-950 text-zinc-100 p-3 rounded border overflow-y-auto max-h-[70vh] font-mono">
        {bufferRef.current.length > 0 ? bufferRef.current.join('\n') : 'Waiting for logs…'}
      </pre>
    </div>
  )
}
