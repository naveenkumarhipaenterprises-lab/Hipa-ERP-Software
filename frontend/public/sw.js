/*
 * Service worker for the installable app (Windows, Android, iOS "Add to Home Screen").
 * Deliberately minimal so an update can never serve stale code:
 *  - /api/ requests are NEVER touched: attendance, logins and data always go to the server.
 *  - Pages (navigations) always come from the network; the cached copy is only a fallback when offline.
 *  - Hashed build files under /assets/ are cached after first use (their names change on every release).
 */
const CACHE = 'hipa-erp-v1'

self.addEventListener('install', () => self.skipWaiting())

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) {
    return // straight to the network, never cached
  }
  if (event.request.mode === 'navigate') {
    // Network first: always the newest app; the cached page only when offline
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const copy = response.clone()
          caches.open(CACHE).then((cache) => cache.put('/', copy)).catch(() => {})
          return response
        })
        .catch(() => caches.match('/')),
    )
    return
  }
  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icons/') || url.pathname === '/manifest.webmanifest') {
    // Build files carry a hash in their name, so a cached copy is always the right one
    event.respondWith(
      caches.match(event.request).then(
        (cached) => cached
          || fetch(event.request).then((response) => {
            const copy = response.clone()
            caches.open(CACHE).then((cache) => cache.put(event.request, copy)).catch(() => {})
            return response
          }),
      ),
    )
  }
})
