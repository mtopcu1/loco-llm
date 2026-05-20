import { screen, waitFor } from '@testing-library/react'
import { renderAtRoute } from '@/test/test-utils'

test('renders configs list', async () => {
  renderAtRoute('/configs')
  await waitFor(() => expect(screen.getByText('default')).toBeInTheDocument())
  expect(screen.getByText('user')).toBeInTheDocument()
})
