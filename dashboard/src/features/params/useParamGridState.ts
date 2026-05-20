import { useMemo, useReducer } from 'react'
import {
  applyAllSuggestions,
  applyFilter,
  cloneCells,
  disableAllOptional,
  type ParamCell,
  type ParamFilter,
  type Recommendation,
  resetToDefaults,
  toServeParams,
} from '@/lib/paramCell'

type Action =
  | { type: 'toggle'; key: string }
  | { type: 'set'; key: string; value: unknown }
  | { type: 'applyOne'; key: string; rec: Recommendation }
  | { type: 'applyAll'; recs: Recommendation[] }
  | { type: 'reset' }
  | { type: 'resetDefaults' }
  | { type: 'disableOptional' }
  | { type: 'replaceAll'; cells: ParamCell[] }
  | { type: 'filter'; partial: Partial<ParamFilter> }

interface State {
  initial: ParamCell[]
  cells: ParamCell[]
  filter: ParamFilter
}

function reducer(s: State, a: Action): State {
  switch (a.type) {
    case 'toggle':
      return {
        ...s,
        cells: s.cells.map((c) =>
          c.key === a.key && !c.locked ? { ...c, enabled: !c.enabled } : c,
        ),
      }
    case 'set':
      return {
        ...s,
        cells: s.cells.map((c) =>
          c.key === a.key && !c.locked
            ? { ...c, value: String(a.value ?? ''), enabled: true }
            : c,
        ),
      }
    case 'applyOne':
      return {
        ...s,
        cells: s.cells.map((c) =>
          c.key === a.key && !c.locked
            ? { ...c, enabled: true, value: String(a.rec.suggested_value ?? '') }
            : c,
        ),
      }
    case 'applyAll':
      return { ...s, cells: applyAllSuggestions(s.cells, a.recs) }
    case 'reset':
      return { ...s, cells: cloneCells(s.initial) }
    case 'resetDefaults':
      return { ...s, cells: resetToDefaults(s.cells) }
    case 'disableOptional':
      return { ...s, cells: disableAllOptional(s.cells) }
    case 'replaceAll':
      return { initial: cloneCells(a.cells), cells: cloneCells(a.cells), filter: s.filter }
    case 'filter':
      return { ...s, filter: { ...s.filter, ...a.partial } }
    default:
      return s
  }
}

export function useParamGridState(initial: ParamCell[]) {
  const [state, dispatch] = useReducer(reducer, {
    initial: cloneCells(initial),
    cells: cloneCells(initial),
    filter: { text: '', enabledOnly: false, showLocked: true },
  })

  const visibleCells = useMemo(
    () => applyFilter(state.cells, state.filter),
    [state.cells, state.filter],
  )

  const isDirty = useMemo(
    () => JSON.stringify(state.cells) !== JSON.stringify(state.initial),
    [state.cells, state.initial],
  )

  return {
    cells: state.cells,
    initialCells: state.initial,
    visibleCells,
    filter: state.filter,
    isDirty,
    toggleEnabled: (key: string) => dispatch({ type: 'toggle', key }),
    setValue: (key: string, value: unknown) => dispatch({ type: 'set', key, value }),
    applySuggestion: (key: string, rec: Recommendation) =>
      dispatch({ type: 'applyOne', key, rec }),
    applyAllSuggestions: (recs: Recommendation[]) => dispatch({ type: 'applyAll', recs }),
    resetToDefaults: () => dispatch({ type: 'reset' }),
    resetToSchemaDefaults: () => dispatch({ type: 'resetDefaults' }),
    disableAllOptional: () => dispatch({ type: 'disableOptional' }),
    replaceAll: (cells: ParamCell[]) => dispatch({ type: 'replaceAll', cells }),
    setFilter: (partial: Partial<ParamFilter>) => dispatch({ type: 'filter', partial }),
    serveParams: () => toServeParams(state.cells),
  }
}
