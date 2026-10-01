const AUTH_PAGES = /^\/(login|forgot-password|reset-password)(\/|\?|$)/

/** Where to go after login: only same-app, non-auth paths are allowed; otherwise the dashboard. */
export function safeRedirect(from) {
  if (typeof from !== 'string' || !from.startsWith('/') || from.startsWith('//')) return '/dashboard'
  return AUTH_PAGES.test(from) ? '/dashboard' : from
}
