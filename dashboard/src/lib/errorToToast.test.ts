import { describe, expect, it, vi } from 'vitest'
import { toast } from 'sonner'
import { errorToToast } from './errorToToast'

vi.mock('sonner', () => ({
  toast: { error: vi.fn() },
}))

describe('errorToToast', () => {
  it('maps known ErrorCode to friendly title', () => {
    errorToToast({
      error: {
        code: 'RUNTIME_IN_USE',
        message: 'Runtime is serving config default.',
        details: {},
      },
    })
    expect(toast.error).toHaveBeenCalledWith(
      'Runtime in use',
      expect.objectContaining({ description: 'Runtime is serving config default.' }),
    )
  })
})
