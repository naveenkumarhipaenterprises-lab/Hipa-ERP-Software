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

const CAMPAIGN = { id: 4, name: 'TEST Diwali', platform: 'Instagram', platform_value: 'instagram', objective: 'sales', budget: 5000,
  description: null, start_date: '2026-10-10', end_date: '2026-10-30', status: 'Active', reach: 0, leads: 0, sales: 0,
  can_end: true, can_edit: true }

test('a campaign is edited, and a post is scheduled for it', async ({ page }) => {
  await signIn(page, 'marketing')
  const calls = await mockApi(page, {
    ...MARKETING,
    'GET /api/marketing/options/': { platforms: PLATFORMS, objectives: [{ value: 'sales', label: 'Sales' }], statuses: [] },
    'GET /api/marketing/campaigns/': { count: 1, results: [CAMPAIGN] },
    'PATCH /api/marketing/campaigns/4/': { ...CAMPAIGN, name: 'TEST Diwali Sale', budget: 7500 },
    'POST /api/marketing/posts/': { status: 201, body: { id: 9 } },
  })
  await page.goto('/marketing')
  await page.getByRole('button', { name: 'Edit TEST Diwali' }).click()
  const form = page.getByRole('dialog', { name: 'Edit TEST Diwali' })
  await expect(form.getByLabel(/Campaign name/)).toHaveValue('TEST Diwali')
  await form.getByLabel(/Campaign name/).fill('TEST Diwali Sale')
  await form.getByLabel(/Budget/).fill('7500')
  await form.getByRole('button', { name: 'Save Changes' }).click()
  await expect(page.getByText('Campaign "TEST Diwali Sale" updated')).toBeVisible()
  expect(calls.find((c) => c.key === 'PATCH /api/marketing/campaigns/4/').body).toMatchObject({ name: 'TEST Diwali Sale', budget: 7500 })

  await page.getByRole('button', { name: 'Create Post' }).first().click()
  const post = page.getByRole('dialog', { name: 'Schedule Post' })
  await post.getByLabel(/^Platform/).selectOption('instagram')
  await post.getByLabel(/^Campaign/).selectOption('4')
  await post.getByLabel(/^Caption/).fill('TEST Diwali offer')
  await post.getByRole('button', { name: 'Schedule Post' }).click()
  await expect(post).toHaveCount(0)
  expect(calls.find((c) => c.key === 'POST /api/marketing/posts/').body).toMatchObject({ campaign_id: '4', platform: 'instagram' })
})

test('a Super Admin can delete a scheduled post from the content calendar', async ({ page }) => {
  await signIn(page, 'admin')
  const calls = await mockApi(page, {
    ...MARKETING,
    'GET /api/marketing/posts/': { count: 1, results: [{ id: 9, platform: 'Instagram', scheduled_for: '2026-10-20T10:00:00+05:30',
      caption: 'TEST Diwali offer', campaign: 'TEST Diwali', status: 'Scheduled', is_due: false, can_update: true }] },
    'DELETE /api/records/scheduled_post/9/': { status: 204, body: {} },
  })
  await page.goto('/marketing')
  await page.getByRole('button', { name: 'Content Calendar' }).first().click()
  await page.getByRole('button', { name: 'Delete Instagram post' }).click()
  await page.getByRole('dialog', { name: 'Delete Instagram post?' }).getByRole('button', { name: 'Delete' }).click()
  await expect(page.getByText('Instagram post deleted')).toBeVisible()
  expect(calls.some((c) => c.key === 'DELETE /api/records/scheduled_post/9/')).toBe(true)
})
