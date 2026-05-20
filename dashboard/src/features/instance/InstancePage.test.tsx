import { screen, waitFor } from '@testing-library/react'
import { renderAtRoute } from '@/test/test-utils'

test('shows idle message when nothing is running', async () => {
  renderAtRoute('/instance')
  await waitFor(() => expect(screen.getByText(/nothing is running/i)).toBeInTheDocument())
})
