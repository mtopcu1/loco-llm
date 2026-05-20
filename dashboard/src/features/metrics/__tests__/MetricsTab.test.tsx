import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MetricsTab } from '../MetricsTab'

vi.mock('@/hooks/useMetricsStream', () => ({
  useMetricsStream: vi.fn(() => ({
    latest: { ts: '2026-05-20T07:30:05Z', tps_decode: 99, ttft_ms: 50 },
    buffer: [
      { ts: '2026-05-20T07:30:00Z', tps_decode: 80, ttft_ms: 55 },
      { ts: '2026-05-20T07:30:05Z', tps_decode: 99, ttft_ms: 50 },
    ],
    connected: true,
  })),
}))

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query')
  return {
    ...actual,
    useQuery: vi.fn(({ queryKey }: { queryKey: unknown[] }) => {
      if (queryKey[0] === 'configs') {
        return {
          isPending: false,
          data: { id: 'default', raw: { runtime: 'vllm' } },
        }
      }
      if (queryKey[0] === 'runtimes' && queryKey.length === 1) {
        return {
          isPending: false,
          data: [{ id: 'vllm', has_metrics: true }],
        }
      }
      if (queryKey[0] === 'runtimes' && queryKey[1] === 'vllm') {
        return {
          isPending: false,
          data: {
            id: 'vllm',
            manifest: {
              metrics: {
                fields: {
                  tps_decode: { label: 'Decode TPS', unit: 'tok/s' },
                  ttft_ms: { label: 'TTFT', unit: 'ms' },
                },
              },
            },
          },
        }
      }
      return { isPending: true, data: undefined }
    }),
  }
})

describe('MetricsTab', () => {
  it('renders live metric cards and sparklines', () => {
    render(<MetricsTab configId="default" />)
    expect(screen.getAllByText('Decode TPS')).toHaveLength(2)
    expect(screen.getByText('99.0')).toBeInTheDocument()
    expect(screen.getAllByText('TTFT')).toHaveLength(2)
    expect(document.querySelectorAll('polyline').length).toBeGreaterThan(0)
  })

  it('shows no-metrics message for runtimes without metrics', async () => {
    const { useQuery } = await import('@tanstack/react-query')
    vi.mocked(useQuery).mockImplementation(({ queryKey }: { queryKey: unknown[] }) => {
      if (queryKey[0] === 'configs') {
        return {
          isPending: false,
          data: { id: 'default', raw: { runtime: 'stub-runtime' } },
        } as ReturnType<typeof useQuery>
      }
      if (queryKey[0] === 'runtimes') {
        return {
          isPending: false,
          data: [{ id: 'stub-runtime', has_metrics: false }],
        } as ReturnType<typeof useQuery>
      }
      return { isPending: false, data: undefined } as ReturnType<typeof useQuery>
    })

    render(<MetricsTab configId="default" />)
    expect(screen.getByText(/does not expose live metrics/i)).toBeInTheDocument()
  })
})
