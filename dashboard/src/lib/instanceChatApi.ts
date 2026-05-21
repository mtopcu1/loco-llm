export type ChatRole = 'user' | 'assistant' | 'system' | 'info'

export type UiChatMessage = {
  id: string
  role: ChatRole
  content: string
  meta?: string
}

export type ReadinessResult = {
  ready: boolean
  config_id: string
  port: number
  mode?: string
  runtime?: string | null
  models: string[]
  latency_ms: number
}

import { apiFetch } from '@/lib/apiFetch'

export type ChatCompletionResult = {
  content: string
  ttftMs: number
  tps: number
  completionTokens: number
}

function parseApiError(body: unknown): string {
  if (body && typeof body === 'object' && 'error' in body) {
    const err = (body as { error?: { message?: string } }).error
    if (err?.message) return err.message
  }
  return 'Request failed'
}

export async function fetchReadiness(timeoutSec = 120): Promise<ReadinessResult> {
  const url = `/api/instance/chat/readiness?timeout_sec=${timeoutSec}`
  const res = await apiFetch(url)
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(parseApiError(body))
  }
  return (await res.json()) as ReadinessResult
}

export async function streamChatCompletion(
  messages: Array<{ role: 'user' | 'assistant' | 'system'; content: string }>,
  handlers: {
    onDelta: (text: string) => void
    onFirstToken?: (ttftMs: number) => void
  },
  options?: { maxTokens?: number },
): Promise<ChatCompletionResult> {
  const started = performance.now()
  let firstTokenAt: number | null = null
  let content = ''
  let completionTokens = 0

  const res = await apiFetch('/api/instance/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages,
      stream: true,
      max_tokens: options?.maxTokens ?? 256,
    }),
  })

  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(parseApiError(body))
  }

  const reader = res.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data:')) continue
      const data = trimmed.slice(5).trim()
      if (data === '[DONE]') continue
      try {
        const parsed = JSON.parse(data) as {
          choices?: Array<{
            delta?: { content?: string; reasoning_content?: string }
          }>
          usage?: { completion_tokens?: number }
        }
        const delta = parsed.choices?.[0]?.delta
        const piece = delta?.content ?? delta?.reasoning_content ?? ''
        if (piece) {
          if (firstTokenAt == null) {
            firstTokenAt = performance.now()
            handlers.onFirstToken?.(firstTokenAt - started)
          }
          content += piece
          handlers.onDelta(piece)
        }
        if (parsed.usage?.completion_tokens != null) {
          completionTokens = parsed.usage.completion_tokens
        }
      } catch {
        /* ignore malformed SSE chunks */
      }
    }
  }

  const ended = performance.now()
  const ttftMs = firstTokenAt != null ? firstTokenAt - started : ended - started
  const genMs = firstTokenAt != null ? ended - firstTokenAt : ended - started
  if (completionTokens <= 0) {
    completionTokens = Math.max(1, Math.round(content.length / 4))
  }
  const tps = genMs > 0 ? (completionTokens / genMs) * 1000 : 0

  return { content, ttftMs, tps, completionTokens }
}

export function readinessInfoMessage(r: ReadinessResult): UiChatMessage {
  const models =
    r.models.length > 0 ? r.models.join(', ') : '(no model id from /v1/models)'
  const lines = [
    `Ready — config \`${r.config_id}\``,
    r.runtime ? `Runtime: ${r.runtime}` : null,
    `Port: ${r.port} · probe: ${r.latency_ms} ms`,
    `Loaded model(s): ${models}`,
  ].filter(Boolean) as string[]

  return {
    id: `readiness-${Date.now()}`,
    role: 'info',
    content: lines.join('\n'),
    meta: r.mode,
  }
}
