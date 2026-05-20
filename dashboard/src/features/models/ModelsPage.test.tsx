import { screen, waitFor } from '@testing-library/react'
import { renderAtRoute } from '@/test/test-utils'

test('renders models list', async () => {
  renderAtRoute('/models')
  await waitFor(() => expect(screen.getByText('llama-3')).toBeInTheDocument())
  expect(screen.getByText('Llama 3')).toBeInTheDocument()
})
