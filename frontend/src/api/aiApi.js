import { api, cleanParams as clean } from './client'

/**
 * AI Assistant endpoints (Django REST API -> AI engine).
 * The frontend never generates answers, insights or suggestions itself.
 *
 * GET /ai/status/
 * { available: boolean, message?, models?: [{ value, label }], features?: { web_search?: boolean, attachments?: boolean } }
 *
 * GET /ai/home/
 * { suggestions: string[], insights: [{ id, kind?, title, text, created_at? }], conversations: [{ id, title, updated_at? }] }
 *
 * POST /ai/chat/   { message, conversation_id?, use_company_data, search_web, model? }
 *                  (multipart with a "file" field when a CSV / PDF / Excel file is attached)
 *   ->  { conversation_id, reply, sources?: [{ title, url? }] }
 *
 * GET /ai/conversations/<id>/  ->  { id, title, messages: [{ role: 'user' | 'assistant', text, created_at? }] }
 */
export const aiApi = {
  getStatus: () => api.get('/ai/status/'),
  getHome: () => api.get('/ai/home/'),
  ask: ({ file, ...body }) => (file ? api.upload('/ai/chat/', file, 'file', body) : api.post('/ai/chat/', clean(body))),
  getConversation: (id) => api.get(`/ai/conversations/${id}/`),
}
