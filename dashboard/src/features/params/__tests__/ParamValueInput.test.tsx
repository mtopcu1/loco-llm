import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ParamValueInput } from '../ParamValueInput'
import type { ParamCell } from '@/lib/paramCell'

function cell(overrides: Partial<ParamCell> & Pick<ParamCell, 'key'>): ParamCell {
  return {
    label: overrides.key,
    description: '',
    value: '',
    enabled: true,
    locked: false,
    readonly: false,
    tier: 'common',
    hint: null,
    param_type: 'string',
    ...overrides,
  }
}

describe('ParamValueInput', () => {
  it('renders text input for string type', () => {
    render(
      <ParamValueInput
        cell={cell({ key: 'host', param_type: 'string', value: '127.0.0.1' })}
        onChange={vi.fn()}
      />,
    )
    const input = screen.getByLabelText('host value')
    expect(input).toHaveAttribute('type', 'text')
    expect(input).toHaveValue('127.0.0.1')
  })

  it('renders number input for int type', () => {
    render(
      <ParamValueInput cell={cell({ key: 'port', param_type: 'int', value: '8000' })} onChange={vi.fn()} />,
    )
    expect(screen.getByLabelText('port value')).toHaveAttribute('type', 'number')
  })

  it('renders switch for bool type', () => {
    render(
      <ParamValueInput cell={cell({ key: 'verbose', param_type: 'bool', value: 'true' })} onChange={vi.fn()} />,
    )
    expect(screen.getByRole('switch', { name: 'verbose value' })).toBeInTheDocument()
  })

  it('renders path input with browse button', () => {
    render(
      <ParamValueInput
        cell={cell({ key: 'gguf_path', param_type: 'path', value: '/models/x.gguf' })}
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByLabelText('gguf_path value')).toBeInTheDocument()
    expect(screen.getByLabelText('Browse')).toBeInTheDocument()
  })

  it('renders select for enum type with choices', () => {
    render(
      <ParamValueInput
        cell={cell({
          key: 'mode',
          param_type: 'enum',
          value: 'fast',
          choices: ['fast', 'quality'],
        })}
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByRole('combobox', { name: 'mode value' })).toBeInTheDocument()
  })

  it('disables input when cell is locked', () => {
    render(
      <ParamValueInput cell={cell({ key: 'port', locked: true, value: '8000' })} onChange={vi.fn()} />,
    )
    expect(screen.getByLabelText('port value')).toBeDisabled()
  })

  it('disables input when cell is not enabled', () => {
    render(
      <ParamValueInput cell={cell({ key: 'port', enabled: false, value: '' })} onChange={vi.fn()} />,
    )
    expect(screen.getByLabelText('port value')).toBeDisabled()
  })
})
