import { expect, test } from '@playwright/test'
import { mockApi, SHELL, signIn } from './helpers'

const PAGES = ['/dashboard', '/sales', '/inventory', '/customers', '/production', '/marketing', '/supply-chain', '/quality', '/finance', '/reports', '/ai-assistant', '/settings']
const WIDTHS = { laptop: 1366, tablet: 768, phone: 375 }

// Pages get empty replies, so this checks the layout itself; long-data layouts were checked during the responsive step
for (const [device, width] of Object.entries(WIDTHS)) {
  test(`no page scrolls sideways on ${device} (${width}px)`, async ({ page }) => {
    test.setTimeout(120_000) // visits 13 pages; the dev server compiles each on first visit
    await page.setViewportSize({ width, height: 900 })
    await signIn(page, 'admin', 'TEST Administrator With A Long Name')
    await mockApi(page, SHELL)
    for (const path of ['/login', ...PAGES]) {
      await page.goto(path)
      await page.waitForLoadState('networkidle')
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)
      expect(overflow, `${path} at ${width}px`).toBeLessThanOrEqual(0)
    }
  })
}
