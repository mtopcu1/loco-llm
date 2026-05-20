import { screen, waitFor } from '@testing-library/react'
import { renderAtRoute } from '@/test/test-utils'

test('renders overview cards from /api/overview', async () => {
  renderAtRoute('/')
  await waitFor(() => expect(screen.getByText(/3 models/i)).toBeInTheDocument())
  expect(screen.getByText(/5 configs/i)).toBeInTheDocument()
  expect(screen.getByText(/idle/i)).toBeInTheDocument()
})
