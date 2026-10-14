import { expect, test } from '@playwright/test'
import { mockApi, SHELL, signIn } from './helpers'

const PLATFORMS = [{ value: 'instagram', label: 'Instagram' }, { value: 'youtube', label: 'YouTube' }]
const EMPTY = { count: 0, results: [] }

const MARKETING = {
  ...SHELL,
  'GET /api/marketing/overview/': { kpis: {}, channels: [], top_content: [], insights: {} },
  'GET /api/marketing/performance/': [],
  'GET /api/marketing/audience/': [],
  'GET /api/marketing/options/': { platforms: PLATFORMS, objectives: [], statuses: [] },
  'GET /api/marketing/campaigns/': EMPTY,
  'GET /api/marketing/posts/': EMPTY,
}

test('marketing data: daily numbers, content and audience are entered from the dashboard', async ({ page }) => {
  await signIn(page, 'marketing')
  let metrics = []
  const calls = await mockApi(page, {
    ...MARKETING,
    'GET /api/marketing/metrics/': () => ({ count: metrics.length, results: metrics }),
    'POST /api/marketing/metrics/': () => {
      metrics = [{ id: 1, date: '2026-10-13', platform: 'Instagram', platform_value: 'instagram', campaign: null, campaign_id: null,
        reach: 1200, engagement: 300, website_visitors: 80, leads: 6, sales_amount: 4500.5 }]
      return { status: 201, body: metrics[0] }
    },
    'GET /api/marketing/content/': EMPTY,
    'POST /api/marketing/content/': { status: 201, body: { id: 2, title: 'TEST Sambar reel', platform: 'Instagram' } },
    'GET /api/marketing/audience-segments/': EMPTY,
  })
  await page.goto('/marketing')
  await expect(page.getByText('Reach, engagement and visitors appear once daily numbers are entered (Enter Data).')).toBeVisible()
  await page.getByRole('button', { name: 'Enter Data' }).first().click()
  const data = page.getByRole('dialog', { name: 'Marketing Data' })
  await expect(data.getByText('No daily numbers entered yet')).toBeVisible()

  await data.getByRole('button', { name: 'Add daily numbers' }).click()
  const form = page.getByRole('dialog', { name: 'Add daily numbers' })
  await form.getByLabel(/^Date/).fill('2026-10-13')
  await form.getByLabel(/^Platform/).selectOption('instagram')
  await form.getByLabel(/^Reach/).fill('1200')
  await form.getByLabel(/^Sales/).fill('4500.50')
  await form.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByText('Instagram 13 Oct 2026 added')).toBeVisible()
  expect(calls.find((c) => c.key === 'POST /api/marketing/metrics/').body).toMatchObject({ date: '2026-10-13', platform: 'instagram', reach: 1200, sales_amount: 4500.5 })
  await expect(data.getByRole('cell', { name: '1,200' })).toBeVisible()
  await expect(data.getByRole('button', { name: /^Delete / })).toHaveCount(0) // deleting is for Super Admins
  expect(calls.filter((c) => c.key === 'GET /api/marketing/overview/').length).toBeGreaterThan(1) // the dashboard refreshed

  await data.getByRole('tab', { name: 'Content' }).click()
  await data.getByRole('button', { name: 'Add content' }).click()
  const content = page.getByRole('dialog', { name: 'Add content' })
  await content.getByLabel(/^Title/).fill('TEST Sambar reel')
  await content.getByLabel(/^Platform/).selectOption('instagram')
  await content.getByLabel(/^Views/).fill('5000')
  await content.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByText('TEST Sambar reel added')).toBeVisible()

  await data.getByRole('tab', { name: 'Audience' }).click()
  await data.getByRole('button', { name: 'Add audience figure' }).click()
  const audience = page.getByRole('dialog', { name: 'Add audience figure' })
  await audience.getByLabel(/^Platform/).selectOption('instagram')
  await audience.getByLabel(/^Audience group/).fill('25-34')
  await audience.getByLabel(/^Share of audience/).fill('120')
  await audience.getByRole('button', { name: 'Save' }).click()
  await expect(audience.getByText('A share can be at most 100%')).toBeVisible()
  expect(calls.some((c) => c.key === 'POST /api/marketing/audience-segments/')).toBe(false)
})

test('marketing data: a load error is shown, not an empty list', async ({ page }) => {
  await signIn(page, 'marketing')
  await mockApi(page, { ...MARKETING, 'GET /api/marketing/metrics/': { status: 500, body: { detail: 'TEST server error' } } })
  await page.goto('/marketing')
  await page.getByRole('button', { name: 'Enter Data' }).first().click()
  const data = page.getByRole('dialog', { name: 'Marketing Data' })
  await expect(data.getByRole('alert')).toBeVisible()
  await expect(data.getByText('No daily numbers entered yet')).toHaveCount(0)
})
