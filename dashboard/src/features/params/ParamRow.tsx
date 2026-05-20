import { HelpCircle, Lock } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { TableCell, TableRow } from '@/components/ui/table'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { diffBadge, type ParamCell, type Recommendation } from '@/lib/paramCell'
import { ParamValueInput } from './ParamValueInput'

type Props = {
  cell: ParamCell
  initialCell?: ParamCell
  recommendation?: Recommendation
  readOnly?: boolean
  onToggle: (key: string) => void
  onSetValue: (key: string, value: unknown) => void
  onApplySuggestion: (key: string, rec: Recommendation) => void
}

const badgeClass: Record<ReturnType<typeof diffBadge>, string> = {
  default: 'bg-zinc-100 text-zinc-700 border-zinc-200',
  modified: 'bg-blue-100 text-blue-800 border-blue-200',
  locked: 'bg-amber-100 text-amber-800 border-amber-200',
}

export function ParamRow({
  cell,
  initialCell,
  recommendation,
  readOnly = false,
  onToggle,
  onSetValue,
  onApplySuggestion,
}: Props) {
  const badge = diffBadge(cell, initialCell)
  const toggleDisabled = readOnly || cell.locked || cell.required === true

  return (
    <TableRow data-testid={`param-row-${cell.key}`}>
      <TableCell>
        <Checkbox
          checked={cell.enabled}
          disabled={toggleDisabled}
          onCheckedChange={() => onToggle(cell.key)}
          aria-label={`Enable ${cell.key}`}
        />
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-2">
          <code className="text-xs">{cell.key}</code>
          <Badge variant="outline" className={badgeClass[badge]}>
            {badge}
          </Badge>
        </div>
      </TableCell>
      <TableCell>
        <ParamValueInput
          cell={cell}
          onChange={(value) => onSetValue(cell.key, value)}
        />
      </TableCell>
      <TableCell>
        {recommendation && !readOnly && !cell.locked ? (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-zinc-600">{String(recommendation.suggested_value)}</span>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => onApplySuggestion(cell.key, recommendation)}
            >
              Apply
            </Button>
          </div>
        ) : null}
      </TableCell>
      <TableCell>
        {cell.locked ? (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="inline-flex text-amber-600" aria-label="Locked">
                  <Lock className="size-4" />
                </span>
              </TooltipTrigger>
              <TooltipContent>
                {cell.readonly ? 'Read-only (bound to model)' : 'Required parameter'}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        ) : null}
      </TableCell>
      <TableCell>
        {cell.description ? (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" className="text-zinc-400 hover:text-zinc-600" aria-label="Description">
                  <HelpCircle className="size-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">{cell.description}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        ) : null}
      </TableCell>
    </TableRow>
  )
}
