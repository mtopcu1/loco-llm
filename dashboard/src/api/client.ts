import createClient from 'openapi-fetch'
import type { paths } from './generated'
import { API_BASE, fetchWithInsecure } from '@/lib/apiFetch'

function testFetch(): typeof fetch | undefined {
  if (!import.meta.env.VITEST) return undefined
  return (input, init) => {
    if (input instanceof Request) {
      return fetchWithInsecure(input.url, {
        method: input.method,
        headers: input.headers,
        body: input.body,
      })
    }
    return fetchWithInsecure(input, init)
  }
}

export const api = createClient<paths>({
  baseUrl: API_BASE,
  fetch: testFetch() ?? fetchWithInsecure,
})
