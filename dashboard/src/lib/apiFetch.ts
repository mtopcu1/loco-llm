import { useAppStore } from '@/store'

/** API prefix used by the dashboard (proxied to loco webapi in dev). */
export const API_BASE = import.meta.env.VITEST ? 'http://localhost/api' : '/api'

function resolveUrl(input: string): string {
  if (input.startsWith('http://') || input.startsWith('https://')) return input
  if (input.startsWith('/api/')) {
    return import.meta.env.VITEST
      ? `http://localhost${input}`
      : input
  }
  if (input.startsWith('/')) {
    return `${API_BASE}${input}`
  }
  return input
}

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return resolveUrl(input)
  if (input instanceof Request) return resolveUrl(input.url)
  return resolveUrl(input.toString())
}

/** `fetch` that applies the insecure-banner header and honors the test base URL. */
export const fetchWithInsecure: typeof fetch = async (input, init) => {
  const response = await fetch(requestUrl(input), init)
  useAppStore.getState().setInsecure(response.headers.get('x-localllm-insecure') === 'true')
  return response
}

/** @deprecated use fetchWithInsecure */
export const apiFetch = fetchWithInsecure
