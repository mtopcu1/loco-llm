import { screen, waitFor } from '@testing-library/react'
import { renderAtRoute } from '@/test/test-utils'

test('renders stored and resolved settings', async () => {
  renderAtRoute('/settings')
  await waitFor(() => expect(screen.getByText('Stored')).toBeInTheDocument())
  expect(screen.getByText('Resolved')).toBeInTheDocument()
  expect(screen.getByText('~/llm-data')).toBeInTheDocument()
})
