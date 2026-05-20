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

  constructor(url: string) {
    this.url = url
    MockEventSource.instances.push(this)
    queueMicrotask(() => this.onopen?.(new Event('open')))
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
