import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { renderAtRoute } from '@/test/test-utils'

const server = setupServer(
  http.get('http://localhost/api/runtimes', () =>
    HttpResponse.json([
      { id: 'llama.cpp', kind: 'official', installed: false },
    ]),
  ),
  http.post('http://localhost/api/runtimes/llama.cpp/install', () =>
    HttpResponse.json({ job_id: 'job1' }),
  ),
  http.get('http://localhost/api/jobs', () => HttpResponse.json([])),
)

test('install triggers job mutation', async () => {
  server.listen({ onUnhandledRequest: 'bypass' })
  const user = userEvent.setup()
  renderAtRoute('/runtimes')
  await waitFor(() => expect(screen.getByText('llama.cpp')).toBeInTheDocument())
  await user.click(screen.getByRole('button', { name: 'Install' }))
  await waitFor(() => {
    expect(screen.getByRole('button', { name: 'Install' })).toBeInTheDocument()
  })
  server.close()
})
