import React from 'react'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import { renderAtRoute, renderWithQuery } from '@/test/test-utils'
import { NewConfigWizard } from '../NewConfigWizard'

async function pickStubRuntime(user: ReturnType<typeof userEvent.setup>) {
  const select = await screen.findByLabelText('Runtime')
  await user.selectOptions(select, 'stub-runtime')
}

test('wizard step 1 requires runtime before advancing', async () => {
  const user = userEvent.setup()
  renderWithQuery(<NewConfigWizard />)

  expect(screen.getByText('1. Runtime')).toBeInTheDocument()
  await screen.findByLabelText('Runtime')

  await user.click(screen.getByRole('button', { name: 'Next' }))
  expect(screen.getByRole('alert')).toHaveTextContent(/select an installed runtime/i)
  expect(screen.getByText('1. Runtime')).toBeInTheDocument()
})

test('selecting runtime advances flow to model step', async () => {
  const user = userEvent.setup()
  renderWithQuery(<NewConfigWizard />)

  await pickStubRuntime(user)
  await user.click(screen.getByRole('button', { name: 'Next' }))

  await waitFor(() =>
    expect(screen.getByText(/does not require a model/i)).toBeInTheDocument(),
  )
})

test('params step shows advisor and param grid', async () => {
  const user = userEvent.setup()
  renderWithQuery(<NewConfigWizard />)

  await pickStubRuntime(user)
  await user.click(screen.getByRole('button', { name: 'Next' }))
  await user.selectOptions(screen.getByLabelText('Model'), '__skip__')
  await user.click(screen.getByRole('button', { name: 'Next' }))

  await waitFor(() => expect(screen.getByText('Advisor')).toBeInTheDocument())
  expect(screen.getByText('host')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Apply all suggestions' })).toBeInTheDocument()
})

test('review blocks duplicate config id', async () => {
  const user = userEvent.setup()
  renderWithQuery(<NewConfigWizard />)

  await pickStubRuntime(user)
  await user.click(screen.getByRole('button', { name: 'Next' }))
  await user.click(screen.getByRole('button', { name: 'Next' }))
  await waitFor(() => expect(screen.getByText('host')).toBeInTheDocument())
  await user.click(screen.getByRole('button', { name: 'Next' }))

  await waitFor(() => expect(screen.getByLabelText('Config ID')).toBeInTheDocument())
  await user.clear(screen.getByLabelText('Config ID'))
  await user.type(screen.getByLabelText('Config ID'), 'default')
  await waitFor(() =>
    expect(screen.getByText(/already exists/i)).toBeInTheDocument(),
  )

  await user.click(screen.getByRole('button', { name: 'Save' }))
  expect(screen.getByRole('alert')).toHaveTextContent(/unique config id/i)
})

test('save redirects to config detail on success', async () => {
  const user = userEvent.setup()
  server.use(
    http.post('http://localhost/api/configs', async ({ request }) => {
      const body = (await request.json()) as { id: string }
      return HttpResponse.json({ id: body.id })
    }),
    http.get('http://localhost/api/configs/my-new-config', () =>
      HttpResponse.json({
        id: 'my-new-config',
        source: 'user',
        raw: { runtime: 'stub-runtime', serve: { params: {} } },
        resolved: { runtime: 'stub-runtime', serve: { params: {} } },
      }),
    ),
  )

  renderAtRoute('/configs/new')

  await waitFor(() => expect(screen.getByText('Create a new config')).toBeInTheDocument())

  await pickStubRuntime(user)
  await user.click(screen.getByRole('button', { name: 'Next' }))
  await user.click(screen.getByRole('button', { name: 'Next' }))
  await waitFor(() => expect(screen.getByText('host')).toBeInTheDocument())
  await user.click(screen.getByRole('button', { name: 'Next' }))

  await waitFor(() => expect(screen.getByLabelText('Config ID')).toBeInTheDocument())
  const idInput = screen.getByLabelText('Config ID')
  await user.clear(idInput)
  await user.type(idInput, 'my-new-config')
  await user.click(screen.getByRole('button', { name: 'Save' }))

  await waitFor(() => expect(screen.getByText('my-new-config')).toBeInTheDocument(), {
    timeout: 5000,
  })
})

test('CONFIG_INVALID shows error with go back on save step', async () => {
  const user = userEvent.setup()
  server.use(
    http.post('http://localhost/api/configs', () =>
      HttpResponse.json(
        {
          code: 'CONFIG_INVALID',
          message: 'Configuration validation failed',
          details: { errors: ['port must be numeric'] },
        },
        { status: 400 },
      ),
    ),
  )

  renderWithQuery(<NewConfigWizard />)

  await pickStubRuntime(user)
  await user.click(screen.getByRole('button', { name: 'Next' }))
  await user.click(screen.getByRole('button', { name: 'Next' }))
  await waitFor(() => expect(screen.getByText('host')).toBeInTheDocument())
  await user.click(screen.getByRole('button', { name: 'Next' }))
  await waitFor(() => expect(screen.getByLabelText('Config ID')).toBeInTheDocument())
  await user.click(screen.getByRole('button', { name: 'Save' }))

  await waitFor(() => expect(screen.getByText(/port must be numeric/i)).toBeInTheDocument())
  expect(screen.getByRole('button', { name: 'Go back' })).toBeInTheDocument()
})

test('NewConfigPage shows wizard step 1 at /configs/new', async () => {
  renderAtRoute('/configs/new')
  await waitFor(() => expect(screen.getByText('Create a new config')).toBeInTheDocument())
  expect(screen.getByText('1. Runtime')).toBeInTheDocument()
})
