import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)

class MockEventSource {
  static instances: MockEventSource[] = []
  url: string
  onopen: ((ev: Event) => void) | null = null
  onmessage: ((ev: MessageEvent) => void) | null = null
  onerror: ((ev: Event) => void) | null = null
  private listeners = new Map<string, Array<(ev: MessageEvent) => void>>()

  constructor(url: string) {
    this.url = url
    MockEventSource.instances.push(this)
    queueMicrotask(() => {
      this.onopen?.(new Event('open'))
      if (url.includes('/jobs/') && url.includes('/stream')) {
        this.emit('snapshot', { status: 'running', kind: 'runtime_install' })
      }
    })
  }

  addEventListener(type: string, handler: (ev: MessageEvent) => void) {
    const list = this.listeners.get(type) ?? []
    list.push(handler)
    this.listeners.set(type, list)
  }

  emit(type: string, payload: unknown) {
    const ev = { data: JSON.stringify(payload) } as MessageEvent
    if (type === 'message') {
      this.onmessage?.(ev)
      return
    }
    for (const handler of this.listeners.get(type) ?? []) {
      handler(ev)
    }
  }

  close() {}
}

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' })
  Object.defineProperty(window, 'scrollTo', { value: () => {}, writable: true })
  globalThis.EventSource = MockEventSource as unknown as typeof EventSource
})

afterEach(() => {
  server.resetHandlers()
  MockEventSource.instances = []
  cleanup()
})

afterAll(() => server.close())
