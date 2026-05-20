import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useParamGridState } from '../useParamGridState'
import type { ParamCell, Recommendation } from '@/lib/paramCell'

function cell(overrides: Partial<ParamCell> & Pick<ParamCell, 'key'>): ParamCell {
  return {
    label: overrides.key,
    description: '',
    value: '',
    enabled: false,
    locked: false,
    readonly: false,
    tier: 'common',
    hint: null,
    param_type: 'string',
    ...overrides,
  }
}

const initial = [
  cell({ key: 'port', enabled: true, value: '8000' }),
  cell({ key: 'host', description: 'Bind host' }),
  cell({ key: 'model', locked: true, enabled: true, value: '/m.gguf' }),
]

describe('useParamGridState', () => {
  it('starts clean with all cells visible', () => {
    const { result } = renderHook(() => useParamGridState(initial))
    expect(result.current.isDirty).toBe(false)
    expect(result.current.visibleCells).toHaveLength(3)
  })

  it('toggleEnabled flips optional cells and marks dirty', () => {
    const { result } = renderHook(() => useParamGridState(initial))
    act(() => result.current.toggleEnabled('host'))
    expect(result.current.cells.find((c) => c.key === 'host')?.enabled).toBe(true)
    expect(result.current.isDirty).toBe(true)
  })

  it('toggleEnabled is no-op for locked cells', () => {
    const { result } = renderHook(() => useParamGridState(initial))
    act(() => result.current.toggleEnabled('model'))
    expect(result.current.cells.find((c) => c.key === 'model')?.enabled).toBe(true)
    expect(result.current.isDirty).toBe(false)
  })

  it('setValue updates value and enables row', () => {
    const { result } = renderHook(() => useParamGridState(initial))
    act(() => result.current.setValue('host', '127.0.0.1'))
    const host = result.current.cells.find((c) => c.key === 'host')
    expect(host?.value).toBe('127.0.0.1')
    expect(host?.enabled).toBe(true)
    expect(result.current.isDirty).toBe(true)
  })

  it('applySuggestion sets suggested value', () => {
    const { result } = renderHook(() => useParamGridState(initial))
    const rec: Recommendation = { param_key: 'host', suggested_value: '0.0.0.0', reason: 'test' }
    act(() => result.current.applySuggestion('host', rec))
    expect(result.current.cells.find((c) => c.key === 'host')?.value).toBe('0.0.0.0')
  })

  it('applyAllSuggestions applies all matching recs', () => {
    const { result } = renderHook(() => useParamGridState(initial))
    const recs: Recommendation[] = [
      { param_key: 'host', suggested_value: '0.0.0.0', reason: 'a' },
      { param_key: 'port', suggested_value: '9000', reason: 'b' },
    ]
    act(() => result.current.applyAllSuggestions(recs))
    expect(result.current.cells.find((c) => c.key === 'host')?.value).toBe('0.0.0.0')
    expect(result.current.cells.find((c) => c.key === 'port')?.value).toBe('9000')
  })

  it('resetToDefaults restores initial snapshot', () => {
    const { result } = renderHook(() => useParamGridState(initial))
    act(() => result.current.setValue('port', '9000'))
    expect(result.current.isDirty).toBe(true)
    act(() => result.current.resetToDefaults())
    expect(result.current.cells).toEqual(initial)
    expect(result.current.isDirty).toBe(false)
  })

  it('disableAllOptional disables unlocked optional rows', () => {
    const { result } = renderHook(() => useParamGridState(initial))
    act(() => result.current.disableAllOptional())
    expect(result.current.cells.find((c) => c.key === 'port')?.enabled).toBe(false)
    expect(result.current.cells.find((c) => c.key === 'model')?.enabled).toBe(true)
  })

  it('setFilter narrows visibleCells', () => {
    const { result } = renderHook(() => useParamGridState(initial))
    act(() => result.current.setFilter({ text: 'bind' }))
    expect(result.current.visibleCells.map((c) => c.key)).toEqual(['host'])
  })

  it('serveParams returns enabled non-empty values', () => {
    const { result } = renderHook(() => useParamGridState(initial))
    expect(result.current.serveParams()).toEqual({ port: '8000', model: '/m.gguf' })
  })

  it('replaceAll replaces state and clears dirty', () => {
    const { result } = renderHook(() => useParamGridState(initial))
    act(() => result.current.setValue('port', '9000'))
    const next = [cell({ key: 'port', enabled: true, value: '7000' })]
    act(() => result.current.replaceAll(next))
    expect(result.current.cells).toEqual(next)
    expect(result.current.isDirty).toBe(false)
  })
})
