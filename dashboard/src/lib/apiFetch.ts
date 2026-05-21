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

/** `fetch` that applies the insecure-banner header and honors the test base URL. */
export async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(resolveUrl(input), init)
  useAppStore.getState().setInsecure(response.headers.get('x-localllm-insecure') === 'true')
  return response
}
