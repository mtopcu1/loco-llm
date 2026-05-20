import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderAtRoute } from '@/test/test-utils'

test('pull dialog validates empty url', async () => {
  const user = userEvent.setup()
  renderAtRoute('/models')
  await waitFor(() => expect(screen.getByText('Pull from HF')).toBeInTheDocument())
  await user.click(screen.getByRole('button', { name: 'Pull from HF' }))
  await user.click(screen.getByRole('button', { name: 'Pull' }))
  await waitFor(() => expect(screen.getByText('URL is required')).toBeInTheDocument())
})
