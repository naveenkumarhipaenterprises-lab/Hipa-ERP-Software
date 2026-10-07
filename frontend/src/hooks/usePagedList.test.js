import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { usePagedList } from './usePagedList'

describe('usePagedList', () => {
  it('counts a chosen filter as filtering, but not the sort order', () => {
    const fetcher = async () => ({ count: 0, results: [] })
    const { result } = renderHook(() => usePagedList(fetcher, { status: '', ordering: 'name' }))
    expect(result.current.filtered).toBe(false) // empty list means "none yet", not "none match"
    act(() => result.current.setFilter('status', 'active'))
    expect(result.current.filtered).toBe(true)
  })
})
