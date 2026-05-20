import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { renderAtRoute } from '@/test/test-utils'

const server = setupServer(
  http.get('http://localhost/api/instance', () => HttpResponse.json({ running: false })),
)

test('shows start controls when idle', async () => {
  server.listen({ onUnhandledRequest: 'bypass' })
  renderAtRoute('/instance')
  await waitFor(() => expect(screen.getByRole('button', { name: 'Start' })).toBeInTheDocument())
  server.close()
})
