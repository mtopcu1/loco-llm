import { useEffect, useRef, useState } from 'react'
import { useSSE } from './useSSE'

export interface Snapshot {
  ts: string
  error?: string
  [field: string]: number | string | null | undefined
}

export function useMetricsStream(enabled = true) {
  const sse = useSSE<Snapshot>({
    url: '/api/instance/metrics/stream',
    enabled,
    eventNames: ['snapshot'],
  })
  const bufferRef = useRef<Snapshot[]>([])
  const [, force] = useState(0)

  useEffect(() => {
    if (!sse.event) return
    bufferRef.current = [...bufferRef.current.slice(-59), sse.event]
    force((n) => n + 1)
  }, [sse.event])

  return { latest: sse.event, buffer: bufferRef.current, connected: sse.connected }
}
