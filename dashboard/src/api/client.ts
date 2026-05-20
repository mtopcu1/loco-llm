import createClient from 'openapi-fetch'
import type { paths } from './generated'
import { useAppStore } from '@/store'

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

const baseFetch = testFetch() ?? fetch

const fetchWithInsecureHeader: typeof fetch = async (input, init) => {
  const response = await baseFetch(input, init)
  const insecure = response.headers.get('x-localllm-insecure') === 'true'
  useAppStore.getState().setInsecure(insecure)
  return response
}

export const api = createClient<paths>({ baseUrl, fetch: fetchWithInsecureHeader })
