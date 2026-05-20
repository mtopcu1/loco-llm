import React from 'react'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ParamGrid } from '../ParamGrid'
import type { ParamCell, Recommendation } from '@/lib/paramCell'

function cell(overrides: Partial<ParamCell> & Pick<ParamCell, 'key'>): ParamCell {
  return {
    label: overrides.key,
    description: overrides.description ?? '',
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

const cells: ParamCell[] = [
  cell({ key: 'port', enabled: true, value: '8000', description: 'HTTP port' }),
  cell({ key: 'host', description: 'Bind host' }),
  cell({ key: 'model', locked: true, enabled: true, value: '/models/x.gguf' }),
]

const recommendations: Recommendation[] = [
  { param_key: 'host', suggested_value: '127.0.0.1', reason: 'local bind' },
]

describe('ParamGrid', () => {
  it('renders all cells initially', () => {
    render(<ParamGrid cells={cells} recommendations={[]} />)
    expect(screen.getByTestId('param-row-port')).toBeInTheDocument()
    expect(screen.getByTestId('param-row-host')).toBeInTheDocument()
    expect(screen.getByTestId('param-row-model')).toBeInTheDocument()
  })

  it('typing in filter narrows the list', async () => {
    const user = userEvent.setup()
    render(<ParamGrid cells={cells} recommendations={[]} />)
    await user.type(screen.getByLabelText('Filter parameters'), 'bind')
    expect(screen.queryByTestId('param-row-port')).not.toBeInTheDocument()
    expect(screen.getByTestId('param-row-host')).toBeInTheDocument()
  })

  it('toggling a row marks dirty and enables save', async () => {
    const user = userEvent.setup()
    render(<ParamGrid cells={cells} recommendations={[]} onSave={vi.fn()} />)
    const save = screen.getByRole('button', { name: 'Save' })
    expect(save).toBeDisabled()
    await user.click(screen.getByLabelText('Enable host'))
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
    expect(save).toBeEnabled()
  })

  it('apply all suggestions applies matching recs', async () => {
    const user = userEvent.setup()
    render(<ParamGrid cells={cells} recommendations={recommendations} onSave={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'Bulk actions' }))
    await user.click(screen.getByRole('menuitem', { name: 'Apply all suggestions' }))
    expect(within(screen.getByTestId('param-row-host')).getByLabelText('host value')).toHaveValue(
      '127.0.0.1',
    )
  })

  it('reset to defaults restores initial', async () => {
    const user = userEvent.setup()
    render(<ParamGrid cells={cells} recommendations={[]} onSave={vi.fn()} />)
    await user.click(screen.getByLabelText('Enable host'))
    await user.click(screen.getByRole('button', { name: 'Bulk actions' }))
    await user.click(screen.getByRole('menuitem', { name: 'Reset to defaults' }))
    expect(screen.queryByText('Unsaved changes')).not.toBeInTheDocument()
    expect(within(screen.getByTestId('param-row-host')).getByLabelText('Enable host')).not.toBeChecked()
  })

  it('save button calls onSave with serveParams shape', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(<ParamGrid cells={cells} recommendations={[]} onSave={onSave} />)
    await user.click(screen.getByLabelText('Enable host'))
    await user.type(within(screen.getByTestId('param-row-host')).getByLabelText('host value'), '127.0.0.1')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(onSave).toHaveBeenCalledWith({ port: '8000', host: '127.0.0.1', model: '/models/x.gguf' })
  })

  it('locked cell value input is disabled', () => {
    render(<ParamGrid cells={cells} recommendations={[]} />)
    expect(within(screen.getByTestId('param-row-model')).getByLabelText('model value')).toBeDisabled()
  })

  it('shows empty filter message', async () => {
    const user = userEvent.setup()
    render(<ParamGrid cells={cells} recommendations={[]} />)
    await user.type(screen.getByLabelText('Filter parameters'), 'no-such-param')
    expect(screen.getByText('No params match the current filter.')).toBeInTheDocument()
  })

  it('hides toolbar in review mode', () => {
    render(<ParamGrid cells={cells} recommendations={[]} mode="review" />)
    expect(screen.queryByLabelText('Filter parameters')).not.toBeInTheDocument()
    expect(screen.getByTestId('param-row-port')).toBeInTheDocument()
  })
})
