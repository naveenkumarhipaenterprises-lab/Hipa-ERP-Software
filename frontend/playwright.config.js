import { defineConfig } from '@playwright/test'

const PORT = 5181

/**
 * End-to-end tests in a real browser (Microsoft Edge, already installed on Windows,
 * so no browser download is needed). Every /api call is answered inside the tests;
 * no backend is required and no test data reaches the app code.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  // The dev server compiles each page on first visit, which can take a few seconds while tests run in parallel
  expect: { timeout: 10_000 },
  use: {
    baseURL: `http://localhost:${PORT}`,
    channel: 'msedge',
    viewport: { width: 1366, height: 900 },
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `npm run dev -- --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
})
