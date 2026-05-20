import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { server } from '@/test/setup'
import { renderAtRoute } from '@/test/test-utils'

vi.mock('@/hooks/useMetricsStream', () => ({
  useMetricsStream: vi.fn((enabled: boolean) =>
    enabled
      ? {
          latest: { ts: '2026-05-20T07:30:05Z', tps_decode: 42.3, ttft_ms: 88 },
          buffer: [],
          connected: true,
        }
      : { latest: null, buffer: [], connected: false },
  ),
}))

test('renders overview cards from /api/overview', async () => {
  renderAtRoute('/')
  await waitFor(() => expect(screen.getByText(/3 models/i)).toBeInTheDocument())
  expect(screen.getByText(/5 configs/i)).toBeInTheDocument()
  expect(screen.getByText(/idle/i)).toBeInTheDocument()
})

describe('OverviewPage live metrics', () => {
  it('shows live TPS and TTFT when instance is running', async () => {
    server.use(
      http.get('http://localhost/api/overview', () =>
        HttpResponse.json({
          version: { cli_version: '1.1.0' },
          instance: { running: true, config_id: 'default' },
          runtimes_count: 2,
          runtimes_installed_count: 1,
          models_count: 3,
          configs_count: 5,
          doctor_summary: {
            default: { ok: 4, warning: 0, error: 0 },
          },
          recent_history: [],
          disk_summary: { data_root_pct_used: 42, models_count: 3, cache_bytes: 1024 },
        }),
      ),
    )
    renderAtRoute('/')
    await waitFor(() => expect(screen.getByText(/running: default/i)).toBeInTheDocument())
    expect(screen.getByText(/TPS 42.3/)).toBeInTheDocument()
    expect(screen.getByText(/TTFT 88 ms/)).toBeInTheDocument()
  })
})
