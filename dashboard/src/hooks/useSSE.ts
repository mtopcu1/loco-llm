import { useEffect, useRef, useState } from 'react'

export interface UseSSEOptions<T> {
  url: string
  enabled?: boolean
  parser?: (raw: string) => T
}

export function useSSE<T = unknown>({ url, enabled = true, parser = JSON.parse as (raw: string) => T }: UseSSEOptions<T>) {
  const [event, setEvent] = useState<T | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<Event | null>(null)
  const retryRef = useRef(0)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!enabled) return

    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null

    const connect = () => {
      if (cancelled) return
      const es = new EventSource(url)
      esRef.current = es
      es.onopen = () => { setConnected(true); retryRef.current = 0; setError(null) }
      es.onmessage = (e) => { try { setEvent(parser(e.data)) } catch { /* ignore */ } }
      es.onerror = (e) => {
        setConnected(false); setError(e); es.close()
        const delay = Math.min(30_000, 1_000 * 2 ** retryRef.current)
        retryRef.current++
        timer = setTimeout(connect, delay)
      }
    }
    connect()

    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
      esRef.current?.close()
    }
  }, [url, enabled, parser])

  return { event, connected, error }
}
