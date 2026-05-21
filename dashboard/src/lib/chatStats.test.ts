import { describe, expect, it } from 'vitest'
import { addSample, emptyAverages, formatTps, formatTtft } from './chatStats'

describe('chatStats', () => {
  it('accumulates running averages', () => {
    let avg = emptyAverages()
    avg = addSample(avg, { ttftMs: 100, tps: 50 })
    avg = addSample(avg, { ttftMs: 200, tps: 70 })
    expect(avg.count).toBe(2)
    expect(avg.avgTtftMs).toBe(150)
    expect(avg.avgTps).toBe(60)
  })

  it('formats values', () => {
    expect(formatTtft(500)).toBe('500 ms')
    expect(formatTtft(1500)).toBe('1.50 s')
    expect(formatTps(42.3)).toBe('42.3 tok/s')
  })
})
