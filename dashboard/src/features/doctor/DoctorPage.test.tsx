import { screen, waitFor } from '@testing-library/react'
import { renderAtRoute } from '@/test/test-utils'

test('renders doctor scopes', async () => {
  renderAtRoute('/doctor')
  await waitFor(() => expect(screen.getByText('python')).toBeInTheDocument())
  expect(screen.getByText('default')).toBeInTheDocument()
})
