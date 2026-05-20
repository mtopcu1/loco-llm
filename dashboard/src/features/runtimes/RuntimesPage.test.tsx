import { screen, waitFor } from '@testing-library/react'
import { renderAtRoute } from '@/test/test-utils'

test('renders runtimes list', async () => {
  renderAtRoute('/runtimes')
  await waitFor(() => expect(screen.getByText('vllm')).toBeInTheDocument())
  expect(screen.getByText('installed', { exact: true })).toBeInTheDocument()
})
