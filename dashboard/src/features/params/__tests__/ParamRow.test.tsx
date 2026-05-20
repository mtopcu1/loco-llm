import React from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Table, TableBody } from '@/components/ui/table'
import { ParamRow } from '../ParamRow'
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

function renderRow(props: Partial<React.ComponentProps<typeof ParamRow>> & { cell: ParamCell }) {
  const defaults = {
    onToggle: vi.fn(),
    onSetValue: vi.fn(),
    onApplySuggestion: vi.fn(),
  }
  return render(
    <Table>
      <TableBody>
        <ParamRow {...defaults} {...props} />
      </TableBody>
    </Table>,
  )
}

describe('ParamRow', () => {
  it('renders key and value input', () => {
    renderRow({ cell: cell({ key: 'port', enabled: true, value: '8000' }) })
    expect(screen.getByText('port')).toBeInTheDocument()
    expect(screen.getByLabelText('port value')).toHaveValue('8000')
  })

  it('calls onToggle when checkbox clicked', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()
    renderRow({ cell: cell({ key: 'host' }), onToggle })
    await user.click(screen.getByLabelText('Enable host'))
    expect(onToggle).toHaveBeenCalledWith('host')
  })

  it('does not toggle locked cells', () => {
    renderRow({ cell: cell({ key: 'model', locked: true, enabled: true }) })
    expect(screen.getByLabelText('Enable model')).toBeDisabled()
  })

  it('shows apply button for recommendations', async () => {
    const user = userEvent.setup()
    const onApplySuggestion = vi.fn()
    const rec: Recommendation = { param_key: 'ctx', suggested_value: '8192', reason: 'fit' }
    renderRow({
      cell: cell({ key: 'ctx' }),
      recommendation: rec,
      onApplySuggestion,
    })
    await user.click(screen.getByRole('button', { name: 'Apply' }))
    expect(onApplySuggestion).toHaveBeenCalledWith('ctx', rec)
  })

  it('shows locked badge state', () => {
    renderRow({ cell: cell({ key: 'model', locked: true, enabled: true, value: 'x' }) })
    expect(screen.getByText('locked')).toBeInTheDocument()
    expect(screen.getByLabelText('Locked')).toBeInTheDocument()
  })
})
