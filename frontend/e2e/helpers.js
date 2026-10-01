/**
 * Test-only helpers. Fake API replies live here and in the spec files; they never
 * become part of the app. Every value is marked TEST.
 */

/** Signs a test user in before the app loads (the same way a real login stores the session). */
export async function signIn(page, role = 'admin', name = 'TEST User') {
  await page.addInitScript(
    ([r, n]) => {
      sessionStorage.setItem('hipa_token', 'test-token')
      sessionStorage.setItem('hipa_user', JSON.stringify({ id: 1, name: n, email: 'test@example.com', role: r }))
    },
    [role, name],
  )
}

/**
 * Answers /api requests. `routes` maps "METHOD /api/path/" to a reply: a body, a function
 * (request) => body, or { status, body }. Anything not listed gets 503, i.e. "backend down".
 * Returns the list of requests the page made, for assertions.
 */
export async function mockApi(page, routes = {}) {
  const calls = []
  // Only real API calls: a glob like **/api/** would also catch the app's own source files under /src/api/
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const req = route.request()
    const url = new URL(req.url())
    // Keys ignore the API version, so "/api/v1/sales/" matches "GET /api/sales/"
    const key = `${req.method()} ${url.pathname.replace(/^\/api\/v\d+\//, '/api/')}`
    let body
    try {
      body = req.postDataJSON()
    } catch {
      body = req.postData() // not JSON (e.g. a file upload)
    }
    calls.push({ key, search: url.search, body })
    let reply = routes[key]
    if (typeof reply === 'function') reply = reply(req, url)
    if (reply === undefined) return route.fulfill({ status: 503, body: '' })
    const isWrapped = reply && typeof reply === 'object' && 'status' in reply && 'body' in reply
    await route.fulfill({
      status: isWrapped ? reply.status : 200,
      contentType: 'application/json',
      body: JSON.stringify(isWrapped ? reply.body : reply),
    })
  })
  return calls
}

/** Empty-but-valid replies for everything the shell (top bar) asks for. */
export const SHELL = { 'GET /api/notifications/': [] }
