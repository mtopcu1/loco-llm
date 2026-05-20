import createClient from 'openapi-fetch'
import type { paths } from './generated'

const baseUrl = import.meta.env.VITEST ? 'http://localhost/api' : '/api'

function testFetch(): typeof fetch | undefined {
  if (!import.meta.env.VITEST) return undefined
  return (input, init) => {
    if (input instanceof Request) {
      return fetch(input.url, {
        method: input.method,
        headers: input.headers,
        body: input.body,
      })
    }
    return fetch(input, init)
  }
}

export const api = createClient<paths>({ baseUrl, fetch: testFetch() })
