import { describe, expect, it } from 'vitest'
import {
  applyAllSuggestions,
  applyFilter,
  applySuggestion,
  diffBadge,
  disableAllOptional,
  resetToDefaults,
  toServeParams,
  type ParamCell,
  type Recommendation,
} from '../paramCell'

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

describe('applyFilter', () => {
  const cells = [
    cell({ key: 'host', description: 'Bind address', enabled: true }),
    cell({ key: 'port', description: 'HTTP port', enabled: false }),
    cell({ key: 'ctx', description: 'Context length', enabled: true, locked: true }),
  ]

  it('returns all cells for empty filter', () => {
    expect(
      applyFilter(cells, { text: '', enabledOnly: false, showLocked: true }),
    ).toHaveLength(3)
  })

  it('filters by key', () => {
    const out = applyFilter(cells, { text: 'port', enabledOnly: false, showLocked: true })
    expect(out.map((c) => c.key)).toEqual(['port'])
  })

  it('filters by description', () => {
    const out = applyFilter(cells, { text: 'context', enabledOnly: false, showLocked: true })
    expect(out.map((c) => c.key)).toEqual(['ctx'])
  })

  it('filters enabled only', () => {
    const out = applyFilter(cells, { text: '', enabledOnly: true, showLocked: true })
    expect(out.map((c) => c.key)).toEqual(['host', 'ctx'])
  })

  it('hides locked when showLocked is false', () => {
    const out = applyFilter(cells, { text: '', enabledOnly: false, showLocked: false })
    expect(out.map((c) => c.key)).toEqual(['host', 'port'])
  })

  it('returns empty for empty input', () => {
    expect(applyFilter([], { text: 'x', enabledOnly: false, showLocked: true })).toEqual([])
  })
})

describe('applySuggestion', () => {
  const rec: Recommendation = { param_key: 'ctx', suggested_value: '8192', reason: 'VRAM fit' }

  it('enables and sets value', () => {
    const out = applySuggestion(cell({ key: 'ctx' }), rec)
    expect(out.enabled).toBe(true)
    expect(out.value).toBe('8192')
  })

  it('is no-op for locked cells', () => {
    const locked = cell({ key: 'ctx', locked: true, value: '4096', enabled: true })
    expect(applySuggestion(locked, rec)).toEqual(locked)
  })
})

describe('applyAllSuggestions', () => {
  it('applies matching recommendations only', () => {
    const cells = [cell({ key: 'ctx' }), cell({ key: 'port' })]
    const recs: Recommendation[] = [
      { param_key: 'ctx', suggested_value: '8192', reason: 'fit' },
    ]
    const out = applyAllSuggestions(cells, recs)
    expect(out[0]?.value).toBe('8192')
    expect(out[1]?.enabled).toBe(false)
  })
})

describe('resetToDefaults', () => {
  it('clears optional cells to schema default', () => {
    const cells = [
      cell({ key: 'port', enabled: true, value: '9000', default: '8000' }),
      cell({ key: 'host', enabled: true, value: '0.0.0.0' }),
    ]
    const out = resetToDefaults(cells)
    expect(out[0]).toMatchObject({ enabled: false, value: '8000' })
    expect(out[1]).toMatchObject({ enabled: false, value: '' })
  })

  it('leaves locked cells unchanged', () => {
    const locked = cell({ key: 'model', locked: true, enabled: true, value: '/models/x.gguf' })
    expect(resetToDefaults([locked])[0]).toEqual(locked)
  })
})

describe('disableAllOptional', () => {
  it('disables non-required optional cells', () => {
    const cells = [
      cell({ key: 'port', enabled: true }),
      cell({ key: 'host', enabled: true, required: true }),
      cell({ key: 'ctx', enabled: true, locked: true }),
    ]
    const out = disableAllOptional(cells)
    expect(out[0]?.enabled).toBe(false)
    expect(out[1]?.enabled).toBe(true)
    expect(out[2]?.enabled).toBe(true)
  })
})

describe('diffBadge', () => {
  it('returns locked for locked cells', () => {
    expect(diffBadge(cell({ key: 'x', locked: true }))).toBe('locked')
  })

  it('returns modified when value differs from initial', () => {
    const initial = cell({ key: 'port', enabled: true, value: '8000' })
    const current = { ...initial, value: '9000' }
    expect(diffBadge(current, initial)).toBe('modified')
  })

  it('returns default when unchanged from initial', () => {
    const initial = cell({ key: 'port', enabled: true, value: '8000' })
    expect(diffBadge(initial, initial)).toBe('default')
  })

  it('uses default field when no initial provided', () => {
    expect(diffBadge(cell({ key: 'port', enabled: true, value: '9000', default: '8000' }))).toBe(
      'modified',
    )
  })
})

describe('toServeParams', () => {
  it('includes only enabled non-empty values', () => {
    const cells = [
      cell({ key: 'port', enabled: true, value: '8000' }),
      cell({ key: 'host', enabled: false, value: '127.0.0.1' }),
      cell({ key: 'threads', enabled: true, value: '' }),
      cell({ key: 'ctx', enabled: true, value: '4096' }),
    ]
    expect(toServeParams(cells)).toEqual({ port: '8000', ctx: '4096' })
  })

  it('returns empty object for empty input', () => {
    expect(toServeParams([])).toEqual({})
  })
})
