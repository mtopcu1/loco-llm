import React from 'react'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { renderWithQuery } from '@/test/test-utils'
import { JobsTray } from './JobsTray'

const runningJob = {
  id: 'job1',
  kind: 'runtime_install',
  status: 'running',
  created_at: '2026-01-01T00:00:00Z',
  started_at: '2026-01-01T00:00:01Z',
  context: { runtime_id: 'vllm' },
  progress: { stage: 'building', percent: null },
}

describe('JobsTray', () => {
  it('shows in-flight jobs and cancel calls API', async () => {
    server.use(
      http.get('http://localhost/api/jobs', () =>
        HttpResponse.json([
          runningJob,
          {
            id: 'job2',
            kind: 'model_pull',
            status: 'succeeded',
            created_at: '2026-01-01T00:00:00Z',
            context: {},
          },
        ]),
      ),
    )
    const user = userEvent.setup()
    renderWithQuery(
      <div className="w-56 flex flex-col h-96">
        <JobsTray />
      </div>,
    )
    await waitFor(() => expect(screen.getByText(/runtime install/i)).toBeInTheDocument())
    expect(screen.queryByText(/pull model/i)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '×' }))
  })
})
