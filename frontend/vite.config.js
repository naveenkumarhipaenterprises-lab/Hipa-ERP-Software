import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // API_PROXY_TARGET has no VITE_ prefix, so it stays in the dev server and is never bundled
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [react()],
    server: {
      port: 5173,
      // Forward /api calls to the Django backend during development
      proxy: {
        '/api': {
          target: env.API_PROXY_TARGET || 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
    // Unit and component tests (Vitest). Browser tests live in e2e/ and run with Playwright.
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.js'],
      include: ['src/**/*.test.{js,jsx}'],
      css: false,
      restoreMocks: true,
    },
  }
})
