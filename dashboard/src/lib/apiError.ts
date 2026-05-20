export type ApiErrorBody = {
  code: string
  message: string
  details?: Record<string, unknown>
  fix_hint?: string | null
}

export function getApiError(error: unknown): ApiErrorBody | null {
  if (!error || typeof error !== 'object') return null
  const wrapped = error as { error?: ApiErrorBody }
  if (wrapped.error?.code) return wrapped.error
  return null
}
