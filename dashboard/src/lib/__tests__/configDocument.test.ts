import { describe, expect, it } from 'vitest'
import { buildConfigPutBody, parseConfigDetail, parseConfigDocument } from '@/lib/configDocument'

describe('parseConfigDocument', () => {
  it('prefers raw over resolved for runtime and model', () => {
    const doc = parseConfigDocument(
      { runtime: 'vllm', model: 'm1', serve: { port: 8000, params: { a: 1 } } },
      { runtime: 'other' },
    )
    expect(doc.runtime).toBe('vllm')
    expect(doc.model).toBe('m1')
    expect(doc.serve?.port).toBe(8000)
    expect(doc.serve?.params).toEqual({ a: 1 })
  })

  it('falls back to resolved when raw is missing', () => {
    const doc = parseConfigDocument(undefined, { runtime: 'ollama' })
    expect(doc.runtime).toBe('ollama')
  })
})

describe('parseConfigDetail', () => {
  it('extracts runtimeId for metrics and params views', () => {
    const parsed = parseConfigDetail({
      id: 'default',
      raw: { runtime: 'vllm', model: 'x' },
    })
    expect(parsed.runtimeId).toBe('vllm')
    expect(parsed.modelId).toBe('x')
  })
})

describe('buildConfigPutBody', () => {
  it('merges serve.params without dropping other serve fields', () => {
    const body = buildConfigPutBody(
      'cfg-1',
      { id: 'cfg-1', raw: { runtime: 'vllm', serve: { host: '127.0.0.1', params: { n_ctx: 4096 } } } },
      { n_ctx: 8192, temperature: 0.7 },
    )
    expect(body.id).toBe('cfg-1')
    expect(body.serve).toEqual({
      host: '127.0.0.1',
      params: { n_ctx: 8192, temperature: 0.7 },
    })
  })
})
