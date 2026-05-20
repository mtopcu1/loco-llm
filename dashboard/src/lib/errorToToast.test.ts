import { describe, expect, it, vi, beforeEach } from 'vitest'
import { toast } from 'sonner'
import { errorToToast } from './errorToToast'

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

describe('errorToToast', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('fetch', vi.fn())
  })

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

  it('adds Fix action for parseable POST fix_hint', () => {
    errorToToast({
      error: {
        code: 'RUNTIME_NOT_INSTALLED',
        message: 'Install vllm first.',
        fix_hint: 'POST /api/runtimes/vllm/install',
      },
    })
    expect(toast.error).toHaveBeenCalledWith(
      'Runtime not installed',
      expect.objectContaining({
        action: expect.objectContaining({ label: 'Fix' }),
      }),
    )
  })
})
