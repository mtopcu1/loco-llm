import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PerformanceMetricsCard } from '../PerformanceMetricsCard'
import { QueryWrapper } from '@/test/test-utils'

describe('PerformanceMetricsCard', () => {
  it('renders aggregated metrics from API', async () => {
    render(
      <QueryWrapper>
        <PerformanceMetricsCard configId="default" />
      </QueryWrapper>,
    )
    await waitFor(() => expect(screen.getByText('Performance')).toBeInTheDocument())
    expect(screen.getByText(/no metrics yet/i)).toBeInTheDocument()
  })
})
