import React from 'react'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { toast } from 'sonner'
import { ParamsView } from './ParamsView'
import { QueryWrapper } from '@/test/test-utils'
import { server } from '@/test/setup'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

describe('ParamsView', () => {
  beforeEach(() => {
    vi.mocked(toast.success).mockClear()
  })

  it('loads grid, toggles a row, saves via PUT, and shows success toast', async () => {
    const user = userEvent.setup()
    let putBody: Record<string, unknown> | undefined

    server.use(
      http.put('http://localhost/api/configs/:id', async ({ request }) => {
        putBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({ id: 'default' })
      }),
    )

    render(
      <QueryWrapper>
        <ParamsView configId="default" />
      </QueryWrapper>,
    )

    await waitFor(() => expect(screen.getByTestId('param-row-port')).toBeInTheDocument())

    const portRow = screen.getByTestId('param-row-port')
    await user.clear(within(portRow).getByLabelText('port value'))
    await user.type(within(portRow).getByLabelText('port value'), '9000')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(putBody).toBeDefined())
    const serve = putBody?.serve as { params?: Record<string, unknown> }
    expect(serve?.params).toMatchObject({ host: '127.0.0.1', port: '9000' })
    expect(toast.success).toHaveBeenCalledWith('Params saved')
  })
})
