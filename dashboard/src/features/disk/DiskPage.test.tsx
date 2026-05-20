import { screen, waitFor } from '@testing-library/react'
import { renderAtRoute } from '@/test/test-utils'

test('renders disk summary', async () => {
  renderAtRoute('/disk')
  await waitFor(() => expect(screen.getByText('llama-3')).toBeInTheDocument())
  expect(screen.getByText(/42%/i)).toBeInTheDocument()
})
