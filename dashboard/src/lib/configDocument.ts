/** Parsed launch-config document shared by config detail, params, and metrics views. */

export type ConfigServeBlock = {
  host?: string
  port?: number
  params?: Record<string, unknown>
}

export type ConfigDocument = {
  id?: string
  runtime?: string
  model?: string
  serve?: ConfigServeBlock
}

export type ConfigDetailResponse = {
  id: string
  source?: string
  raw?: unknown
  resolved?: unknown
}

export type ParsedConfig = {
  detail: ConfigDetailResponse
  document: ConfigDocument
  runtimeId: string
  modelId?: string
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined
}

export function parseConfigDocument(
  raw: unknown,
  resolved?: unknown,
): ConfigDocument {
  const base = asRecord(raw) ?? asRecord(resolved) ?? {}
  const serveRaw = asRecord(base.serve)
  const serve: ConfigServeBlock | undefined = serveRaw
    ? {
        host: typeof serveRaw.host === 'string' ? serveRaw.host : undefined,
        port: typeof serveRaw.port === 'number' ? serveRaw.port : undefined,
        params: asRecord(serveRaw.params) as Record<string, unknown> | undefined,
      }
    : undefined

  return {
    id: typeof base.id === 'string' ? base.id : undefined,
    runtime: typeof base.runtime === 'string' ? base.runtime : undefined,
    model: typeof base.model === 'string' ? base.model : undefined,
    serve,
  }
}

export function parseConfigDetail(data: unknown): ParsedConfig {
  const detail = data as ConfigDetailResponse
  const document = parseConfigDocument(detail.raw, detail.resolved)
  return {
    detail,
    document,
    runtimeId: document.runtime ?? '',
    modelId: document.model,
  }
}

/** Body for PUT /configs/{id} preserving non-serve fields while updating serve.params. */
export function buildConfigPutBody(
  configId: string,
  detail: ConfigDetailResponse,
  serveParams: Record<string, unknown>,
): Record<string, unknown> {
  const document = parseConfigDocument(detail.raw, detail.resolved)
  const serve = document.serve ?? {}
  return {
    ...document,
    id: configId,
    serve: { ...serve, params: serveParams },
  }
}
