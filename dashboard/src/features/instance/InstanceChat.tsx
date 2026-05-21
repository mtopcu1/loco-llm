import { useCallback, useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  addSample,
  emptyAverages,
  formatTps,
  formatTtft,
  type ChatAverages,
} from '@/lib/chatStats'
import {
  fetchReadiness,
  readinessInfoMessage,
  streamChatCompletion,
  type UiChatMessage,
} from '@/lib/instanceChatApi'

const READINESS_PROBE: Array<{ role: 'user'; content: string }> = [
  {
    role: 'user',
    content: 'Reply with exactly one word: ready',
  },
]

function nextId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

export type InstanceChatProps = {
  configId: string
  port?: number
}

export function InstanceChat({ configId, port }: InstanceChatProps) {
  const [messages, setMessages] = useState<UiChatMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [checking, setChecking] = useState(false)
  const [averages, setAverages] = useState<ChatAverages>(emptyAverages)
  const lastConfigRef = useRef<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  const append = useCallback((msg: UiChatMessage) => {
    setMessages((prev) => [...prev, msg])
  }, [])

  const runReadiness = useCallback(
    async (trigger: 'mount' | 'switch') => {
      setChecking(true)
      append({
        id: nextId(),
        role: 'info',
        content:
          trigger === 'switch'
            ? `Switch complete — waiting for \`${configId}\` to answer on port ${port ?? '…'}…`
            : `Checking readiness for \`${configId}\`…`,
      })
      try {
        const r = await fetchReadiness(120)
        append(readinessInfoMessage(r))
        append({ id: nextId(), role: 'user', content: READINESS_PROBE[0].content })
        setBusy(true)
        let probeText = ''
        const result = await streamChatCompletion(READINESS_PROBE, {
          onDelta: (t) => {
            probeText += t
          },
        })
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            role: 'assistant',
            content: probeText || result.content || '(empty)',
            meta: `probe · TTFT ${formatTtft(result.ttftMs)} · ${formatTps(result.tps)}`,
          },
        ])
        setAverages((avg) => addSample(avg, { ttftMs: result.ttftMs, tps: result.tps }))
      } catch (e) {
        append({
          id: nextId(),
          role: 'info',
          content: `Readiness failed: ${e instanceof Error ? e.message : String(e)}`,
        })
      } finally {
        setBusy(false)
        setChecking(false)
      }
    },
    [append, configId, port],
  )

  useEffect(() => {
    if (lastConfigRef.current === configId) return
    lastConfigRef.current = configId
    const trigger = messages.length === 0 ? 'mount' : 'switch'
    void runReadiness(trigger)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only on config change
  }, [configId])

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendUserMessage = async () => {
    const text = input.trim()
    if (!text || busy || checking) return
    setInput('')
    const userMsg: UiChatMessage = { id: nextId(), role: 'user', content: text }
    append(userMsg)
    setBusy(true)
    let assistantId = nextId()
    append({ id: assistantId, role: 'assistant', content: '' })

    try {
      const history = [...messages, userMsg]
        .filter((m) => m.role === 'user' || m.role === 'assistant' || m.role === 'system')
        .map((m) => ({
          role: m.role as 'user' | 'assistant' | 'system',
          content: m.content,
        }))

      const result = await streamChatCompletion(history, {
        onDelta: (piece) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + piece } : m,
            ),
          )
        },
        onFirstToken: (ttftMs) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, meta: `TTFT ${formatTtft(ttftMs)}` }
                : m,
            ),
          )
        },
      })

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: m.content || result.content || '(empty)',
                meta: `TTFT ${formatTtft(result.ttftMs)} · ${formatTps(result.tps)}`,
              }
            : m,
        ),
      )
      setAverages((avg) => addSample(avg, { ttftMs: result.ttftMs, tps: result.tps }))
    } catch (e) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: `Error: ${e instanceof Error ? e.message : String(e)}`,
              }
            : m,
        ),
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="p-4 flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-medium">Chat test</h2>
        <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-600">
          <span>
            Avg TTFT: <strong className="text-zinc-900">{formatTtft(averages.avgTtftMs)}</strong>
            {averages.count > 0 ? ` (n=${averages.count})` : ''}
          </span>
          <span>
            Avg TPS: <strong className="text-zinc-900">{formatTps(averages.avgTps)}</strong>
          </span>
          <Button
            type="button"
            size="xs"
            variant="outline"
            disabled={averages.count === 0}
            onClick={() => setAverages(emptyAverages())}
          >
            Reset averages
          </Button>
        </div>
      </div>

      <div
        className="min-h-[12rem] max-h-80 overflow-y-auto rounded-md border bg-zinc-50/80 p-3 text-sm space-y-3"
        aria-live="polite"
      >
        {messages.length === 0 && (
          <p className="text-zinc-500 text-xs">Messages appear after readiness checks and your prompts.</p>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={
              m.role === 'user'
                ? 'text-right'
                : m.role === 'info'
                  ? 'text-zinc-600 text-xs border-l-2 border-zinc-300 pl-2 whitespace-pre-wrap'
                  : 'text-left'
            }
          >
            {m.role !== 'info' && (
              <span className="text-[10px] uppercase tracking-wide text-zinc-400 mr-2">
                {m.role}
              </span>
            )}
            <span className="whitespace-pre-wrap break-words">{m.content}</span>
            {m.meta && (
              <div className="text-[10px] text-zinc-400 mt-0.5">{m.meta}</div>
            )}
          </div>
        ))}
        <div ref={scrollRef} />
      </div>

      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          void sendUserMessage()
        }}
      >
        <Input
          className="flex-1 font-mono text-sm"
          placeholder="Message the running model…"
          value={input}
          disabled={busy || checking}
          onChange={(e) => setInput(e.target.value)}
        />
        <Button type="submit" disabled={busy || checking || !input.trim()}>
          Send
        </Button>
      </form>
    </Card>
  )
}
