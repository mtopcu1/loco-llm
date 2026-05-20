export type ParamType = 'string' | 'int' | 'float' | 'bool' | 'enum' | 'path'

/** ParamCell shape from GET /configs/{id}/params and /runtimes/{id}/default-params. */
export interface ParamCell {
  key: string
  label: string
  description: string
  value: string
  enabled: boolean
  locked: boolean
  readonly: boolean
  tier: string
  hint: string | null
  param_type: ParamType
  /** Optional schema metadata when present. */
  required?: boolean
  default?: string | null
  choices?: string[]
}

export interface Recommendation {
  param_key: string
  suggested_value: unknown
  reason: string
  confidence?: number
}

export type ParamFilter = {
  text: string
  enabledOnly: boolean
  showLocked: boolean
}

export function applyFilter(cells: ParamCell[], filter: ParamFilter): ParamCell[] {
  const needle = filter.text.trim().toLowerCase()
  return cells.filter((c) => {
    if (filter.enabledOnly && !c.enabled) return false
    if (!filter.showLocked && c.locked) return false
    if (!needle) return true
    const hay = `${c.key} ${c.label} ${c.description ?? ''} ${c.hint ?? ''}`.toLowerCase()
    return hay.includes(needle)
  })
}

export function applySuggestion(cell: ParamCell, rec: Recommendation): ParamCell {
  if (cell.locked) return cell
  return {
    ...cell,
    enabled: true,
    value: String(rec.suggested_value ?? ''),
  }
}

export function applyAllSuggestions(cells: ParamCell[], recs: Recommendation[]): ParamCell[] {
  const map = new Map(recs.map((r) => [r.param_key, r]))
  return cells.map((c) => {
    const r = map.get(c.key)
    return r ? applySuggestion(c, r) : c
  })
}

export function resetToDefaults(cells: ParamCell[]): ParamCell[] {
  return cells.map((c) =>
    c.locked ? c : { ...c, enabled: false, value: c.default ?? '' },
  )
}

export function disableAllOptional(cells: ParamCell[]): ParamCell[] {
  return cells.map((c) => (c.locked || c.required ? c : { ...c, enabled: false }))
}

export function diffBadge(
  cell: ParamCell,
  initial?: ParamCell,
): 'default' | 'modified' | 'locked' {
  if (cell.locked) return 'locked'
  const ref = initial
  if (ref) {
    if (cell.enabled !== ref.enabled || cell.value !== ref.value) return 'modified'
    return 'default'
  }
  const defValue = cell.default ?? ''
  if (cell.enabled && cell.value !== defValue) return 'modified'
  return 'default'
}

export function toServeParams(cells: ParamCell[]): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const c of cells) {
    if (c.enabled && c.value != null && c.value !== '') out[c.key] = c.value
  }
  return out
}

export function cloneCells(cells: ParamCell[]): ParamCell[] {
  return cells.map((c) => ({ ...c }))
}

/** Attach default snapshots for reset/diff helpers. */
export function withDefaults(cells: ParamCell[]): ParamCell[] {
  return cells.map((c) => ({ ...c, default: c.default ?? c.value }))
}

export function proposeConfigId(runtimeId: string, modelId: string | null): string {
  const model = modelId ?? 'nomodel'
  return `${runtimeId}__${model}__default`
}

export function buildConfigBody(args: {
  configId: string
  runtimeId: string
  modelId: string | null
  params: ParamCell[]
}) {
  return {
    id: args.configId,
    runtime: args.runtimeId,
    model: args.modelId || undefined,
    serve: {
      host: '127.0.0.1',
      port: 8000,
      params: toServeParams(args.params),
    },
    readiness: { timeout_seconds: 600 },
  }
}
