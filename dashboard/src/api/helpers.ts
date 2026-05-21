import { api } from '@/api/client'
import type { paths } from '@/api/generated'

type ApiResult<T> = { data?: T; error?: unknown }

/** Unwrap an openapi-fetch call; throw API errors for React Query / mutations. */
export async function unwrapApi<T>(call: () => Promise<ApiResult<T>>): Promise<T> {
  const { data, error } = await call()
  if (error) throw error
  return data as T
}

type PostPaths = {
  [K in keyof paths]: paths[K] extends { post: unknown } ? K : never
}[keyof paths]

type PostOptions<P extends PostPaths> = Parameters<(typeof api)['POST']>[1] extends infer O
  ? P extends keyof O
    ? O[P]
    : never
  : never

/** Typed POST helper (single `as never` boundary for openapi-fetch). */
export async function apiPost<P extends PostPaths>(
  path: P,
  options: PostOptions<P>,
): Promise<unknown> {
  return unwrapApi(() =>
    api.POST(path, options as never) as Promise<ApiResult<unknown>>,
  )
}
