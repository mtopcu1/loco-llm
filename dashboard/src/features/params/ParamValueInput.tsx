import { FolderOpen } from 'lucide-react'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import type { ParamCell } from '@/lib/paramCell'

type Props = {
  cell: ParamCell
  onChange: (value: unknown) => void
}

function boolValue(value: string): boolean {
  return value === 'true' || value === '1' || value.toLowerCase() === 'yes'
}

export function ParamValueInput({ cell, onChange }: Props) {
  const disabled = cell.locked || !cell.enabled
  const placeholder = disabled && !cell.locked ? 'Click to enable' : undefined

  if (cell.param_type === 'bool') {
    return (
      <Switch
        checked={boolValue(cell.value)}
        disabled={disabled}
        onCheckedChange={(checked) => onChange(checked ? 'true' : 'false')}
        aria-label={`${cell.key} value`}
      />
    )
  }

  if (cell.param_type === 'enum' && cell.choices && cell.choices.length > 0) {
    return (
      <Select
        value={cell.value || undefined}
        disabled={disabled}
        onValueChange={(value) => onChange(value)}
      >
        <SelectTrigger className="w-full max-w-xs" aria-label={`${cell.key} value`}>
          <SelectValue placeholder={placeholder ?? 'Select…'} />
        </SelectTrigger>
        <SelectContent>
          {cell.choices.map((choice) => (
            <SelectItem key={choice} value={choice}>
              {choice}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    )
  }

  if (cell.param_type === 'path') {
    return (
      <div className="flex max-w-md items-center gap-1">
        <Input
          value={cell.value}
          disabled={disabled}
          placeholder={placeholder ?? cell.label}
          onChange={(e) => onChange(e.target.value)}
          aria-label={`${cell.key} value`}
        />
        <Button type="button" variant="outline" size="icon" disabled={disabled} aria-label="Browse">
          <FolderOpen className="size-4" />
        </Button>
      </div>
    )
  }

  const inputType = cell.param_type === 'int' || cell.param_type === 'float' ? 'number' : 'text'

  return (
    <Input
      type={inputType}
      value={cell.value}
      disabled={disabled}
      placeholder={placeholder ?? cell.label}
      onChange={(e) => onChange(e.target.value)}
      aria-label={`${cell.key} value`}
      className="max-w-md"
    />
  )
}
