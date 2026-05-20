import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MetricsCards } from '../MetricsCards'

describe('MetricsCards', () => {
  it('renders latest metric values with units', () => {
    render(
      <MetricsCards
        snapshot={{ ts: '2026-05-20T07:30:05Z', tps_decode: 42.3, ttft_ms: 87.5 }}
        fieldMeta={{
          tps_decode: { label: 'Decode TPS', unit: 'tok/s' },
          ttft_ms: { label: 'TTFT', unit: 'ms' },
        }}
      />,
    )
    expect(screen.getByText('Decode TPS')).toBeInTheDocument()
    expect(screen.getByText('42.3')).toBeInTheDocument()
    expect(screen.getByText('tok/s')).toBeInTheDocument()
    expect(screen.getByText('TTFT')).toBeInTheDocument()
    expect(screen.getByText('87.5')).toBeInTheDocument()
  })

  it('shows waiting state when snapshot is empty', () => {
    render(<MetricsCards snapshot={null} />)
    expect(screen.getByText(/waiting for metrics/i)).toBeInTheDocument()
  })
})
