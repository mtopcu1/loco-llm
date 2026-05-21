export type ChatSample = { ttftMs: number; tps: number }

export type ChatAverages = {
  count: number
  avgTtftMs: number | null
  avgTps: number | null
}

export function emptyAverages(): ChatAverages {
  return { count: 0, avgTtftMs: null, avgTps: null }
}

export function addSample(prev: ChatAverages, sample: ChatSample): ChatAverages {
  const count = prev.count + 1
  const avgTtftMs =
    prev.avgTtftMs == null ? sample.ttftMs : (prev.avgTtftMs * prev.count + sample.ttftMs) / count
  const avgTps =
    prev.avgTps == null ? sample.tps : (prev.avgTps * prev.count + sample.tps) / count
  return { count, avgTtftMs, avgTps }
}

export function formatTtft(ms: number | null): string {
  if (ms == null) return '—'
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${Math.round(ms)} ms`
}

export function formatTps(tps: number | null): string {
  if (tps == null) return '—'
  return `${tps.toFixed(1)} tok/s`
}
