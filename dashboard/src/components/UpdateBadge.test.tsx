import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { server } from '@/test/setup'
import { renderWithQuery } from '@/test/test-utils'
import { UpdateBadge } from './UpdateBadge'

const updateAvailable = {
  current: '1.1.0',
  latest: '1.2.0',
  update_available: true,
  release_url: 'https://github.com/example/releases/1.2.0',
}

describe('UpdateBadge', () => {
  it('is hidden when no update is available', async () => {
    server.use(
      http.get('http://localhost/api/update/check', () =>
        HttpResponse.json({
          current: '1.1.0',
          latest: '1.1.0',
          update_available: false,
          release_url: null,
        }),
      ),
    )
    renderWithQuery(<UpdateBadge />)
    await waitFor(() => {
      expect(screen.queryByText(/update available/i)).not.toBeInTheDocument()
    })
  })

  it('shows badge and opens dialog when update is available', async () => {
    const postSpy = vi.fn()
    server.use(
      http.get('http://localhost/api/update/check', () => HttpResponse.json(updateAvailable)),
      http.post('http://localhost/api/update', async ({ request }) => {
        postSpy(await request.url)
        return HttpResponse.json({ job_id: 'job-update' })
      }),
      http.get('http://localhost/api/jobs', () => HttpResponse.json([])),
    )
    const user = userEvent.setup()
    renderWithQuery(<UpdateBadge />)
    await waitFor(() =>
      expect(screen.getByText(/update available: v1\.2\.0/i)).toBeInTheDocument(),
    )
    await user.click(screen.getByRole('button', { name: /update available/i }))
    expect(screen.getByRole('heading', { name: /update available/i })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Update now' }))
    await waitFor(() => expect(postSpy).toHaveBeenCalled())
    expect(String(postSpy.mock.calls[0][0])).toContain('restart_dashboard=true')
  })
})
