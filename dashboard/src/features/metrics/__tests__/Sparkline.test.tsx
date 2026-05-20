import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Sparkline } from '../Sparkline'

describe('Sparkline', () => {
  it('renders polyline with points for three values', () => {
    const { container } = render(<Sparkline values={[1, 2, 3]} />)
    const polyline = container.querySelector('polyline')
    expect(polyline).not.toBeNull()
    const points = polyline!.getAttribute('points')!.trim().split(/\s+/)
    expect(points).toHaveLength(3)
  })

  it('renders empty svg when fewer than two values', () => {
    const { container } = render(<Sparkline values={[1]} />)
    expect(container.querySelector('polyline')).toBeNull()
    expect(container.querySelector('svg')).not.toBeNull()
  })
})
