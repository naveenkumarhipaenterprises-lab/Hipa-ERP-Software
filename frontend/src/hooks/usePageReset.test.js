import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { usePageReset } from './usePageReset'

describe('usePageReset', () => {
  it('goes back to page 1 whenever the filters change, and stays there if they change back', () => {
    const { result, rerender } = renderHook(({ key }) => usePageReset(key), { initialProps: { key: 'a' } })
    act(() => result.current[1](3))
    expect(result.current[0]).toBe(3)
    rerender({ key: 'b' })
    expect(result.current[0]).toBe(1)
    rerender({ key: 'a' })
    expect(result.current[0]).toBe(1)
  })
})
