import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Unmount rendered components and clear stored sessions between tests
afterEach(() => {
  cleanup()
  localStorage.clear()
  sessionStorage.clear()
})

// jsdom has no matchMedia; the layout uses it for the tablet drawer
if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    addEventListener() {},
    removeEventListener() {},
  })
}
