import { api } from './client'

/**
 * Notification endpoints (Django REST API).
 * Expected list response: an array, or { results: [...], unread_count? }, where each item is
 * { id, title, message?, type?: 'info' | 'warning' | 'success' | 'error', created_at, read, link? }
 */
export const notificationsApi = {
  list: () => api.get('/notifications/'),
  markRead: (id) => api.post(`/notifications/${id}/read/`),
  markAllRead: () => api.post('/notifications/mark-all-read/'),
}

/** Accepts either response shape and returns { items, unread }. */
export function normalizeNotifications(data) {
  const items = Array.isArray(data) ? data : Array.isArray(data?.results) ? data.results : []
  const unread = Number.isFinite(data?.unread_count) ? data.unread_count : items.filter((n) => !n.read).length
  return { items, unread }
}
