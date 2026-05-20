import { render, screen } from '@testing-library/react'
import { describe, expect, it, beforeEach } from 'vitest'
import { SecurityBanner } from './SecurityBanner'
import { useAppStore } from '@/store'

describe('SecurityBanner', () => {
  beforeEach(() => {
    useAppStore.setState({ insecure: false })
  })

  it('renders nothing when not insecure', () => {
    const { container } = render(<SecurityBanner />)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows warning banner when insecure', () => {
    useAppStore.setState({ insecure: true })
    render(<SecurityBanner />)
    expect(screen.getByText(/EXPOSED ON NETWORK/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /why this is risky/i })).toHaveAttribute(
      'href',
      '/docs/dashboard-security#risks',
    )
  })
})
