import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { ParamCell, Recommendation } from '@/lib/paramCell'
import { ParamRow } from './ParamRow'
import { useParamGridState } from './useParamGridState'

export interface ParamGridProps {
  cells: ParamCell[]
  recommendations: Recommendation[]
  onSave?: (serveParams: Record<string, unknown>) => Promise<void>
  mode?: 'edit' | 'review'
  saveErrors?: string[]
  saving?: boolean
}

export interface ParamGridHandle {
  getCells: () => ParamCell[]
  applyAllSuggestions: (recs: Recommendation[]) => void
}

export const ParamGrid = forwardRef<ParamGridHandle, ParamGridProps>(function ParamGrid(
  {
    cells,
    recommendations,
    onSave,
    mode = 'edit',
    saveErrors,
    saving = false,
  },
  ref,
) {
  const readOnly = mode === 'review'
  const filterRef = useRef<HTMLInputElement>(null)
  const grid = useParamGridState(cells)

  useImperativeHandle(
    ref,
    () => ({
      getCells: () => grid.cells,
      applyAllSuggestions: (recs: Recommendation[]) => grid.applyAllSuggestions(recs),
    }),
    [grid],
  )

  useEffect(() => {
    grid.replaceAll(cells)
  }, [cells])

  useEffect(() => {
    if (readOnly) return
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
        e.preventDefault()
        filterRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [readOnly])

  const recByKey = useMemo(
    () => new Map(recommendations.map((r) => [r.param_key, r])),
    [recommendations],
  )

  const initialByKey = useMemo(
    () => new Map(grid.initialCells.map((c) => [c.key, c])),
    [grid.initialCells],
  )

  const handleSave = async () => {
    if (!onSave || !grid.isDirty) return
    await onSave(grid.serveParams())
  }

  return (
    <div className="space-y-3">
      {!readOnly && (
        <div className="sticky top-0 z-10 flex flex-wrap items-center gap-3 rounded-md border bg-background p-3">
          <Input
            ref={filterRef}
            placeholder="Filter… (Ctrl+F)"
            value={grid.filter.text}
            onChange={(e) => grid.setFilter({ text: e.target.value })}
            className="max-w-xs"
            aria-label="Filter parameters"
          />
          <label className="flex items-center gap-2 text-sm">
            <Switch
              checked={grid.filter.enabledOnly}
              onCheckedChange={(checked) => grid.setFilter({ enabledOnly: checked })}
              aria-label="Enabled only"
            />
            Enabled only
          </label>
          <label className="flex items-center gap-2 text-sm">
            <Switch
              checked={grid.filter.showLocked}
              onCheckedChange={(checked) => grid.setFilter({ showLocked: checked })}
              aria-label="Show locked"
            />
            Show locked
          </label>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button type="button" variant="outline" size="sm">
                Bulk actions
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem onClick={() => grid.applyAllSuggestions(recommendations)}>
                Apply all suggestions
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => grid.resetToDefaults()}>
                Reset to defaults
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => grid.disableAllOptional()}>
                Disable all optional
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <div className="ml-auto flex items-center gap-2">
            {grid.isDirty ? (
              <Badge variant="outline" className="border-blue-300 text-blue-700">
                Unsaved changes
              </Badge>
            ) : null}
            {onSave ? (
              <Button
                type="button"
                size="sm"
                disabled={!grid.isDirty || saving}
                onClick={() => void handleSave()}
              >
                {saving ? 'Saving…' : 'Save'}
              </Button>
            ) : null}
          </div>
        </div>
      )}

      {saveErrors && saveErrors.length > 0 ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <p className="font-medium">Validation errors</p>
          <ul className="mt-1 list-disc pl-5">
            {saveErrors.map((err) => (
              <li key={err}>{err}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10"> </TableHead>
            <TableHead>key</TableHead>
            <TableHead>value</TableHead>
            <TableHead>suggestion</TableHead>
            <TableHead>locked</TableHead>
            <TableHead>desc</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {grid.visibleCells.length === 0 ? (
            <TableRow>
              <td colSpan={6} className="p-4 text-center text-sm text-zinc-500">
                No params match the current filter.
              </td>
            </TableRow>
          ) : (
            grid.visibleCells.map((c) => (
              <ParamRow
                key={c.key}
                cell={c}
                initialCell={initialByKey.get(c.key)}
                recommendation={recByKey.get(c.key)}
                readOnly={readOnly}
                onToggle={grid.toggleEnabled}
                onSetValue={grid.setValue}
                onApplySuggestion={grid.applySuggestion}
              />
            ))
          )}
        </TableBody>
      </Table>
    </div>
  )
})
