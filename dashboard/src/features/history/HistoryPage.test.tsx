import { screen, waitFor } from '@testing-library/react'
import { renderAtRoute } from '@/test/test-utils'

test('renders history entries', async () => {
  renderAtRoute('/history')
  await waitFor(() => expect(screen.getByText('start')).toBeInTheDocument())
  expect(screen.getByText('stop')).toBeInTheDocument()
})
