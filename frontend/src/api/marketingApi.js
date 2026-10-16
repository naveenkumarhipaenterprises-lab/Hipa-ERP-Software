import { api, cleanParams as clean } from './client'

/**
 * Marketing endpoints (Django REST API).
 *
 * GET /marketing/overview/?range=
 * {
 *   kpis: { reach, engagement, website_visitors, marketing_sales },   // each { value, change? }; marketing_sales in ₹
 *   channels:    [{ name, value }],                  // share of engagement per channel, in %
 *   top_content: [{ id, title, platform?, views?, likes?, shares?, url? }],
 *   insights:    { text?, actions?: string[] },      // from the AI engine; empty until it exists
 * }
 *
 * GET /marketing/performance/?days=30|14|7   ->  [{ label, reach, engagement, website_visitors }]
 * GET /marketing/audience/?platform=         ->  [{ name, value }]   // audience split, e.g. by age group
 *
 * GET /marketing/options/
 * { platforms: [{ value, label }], objectives: [{ value, label }], statuses: [{ value, label }] }
 *
 * GET /marketing/campaigns/?page=&page_size=&search=&status=
 * { count, results: [{ id, name, platform, start_date, end_date, status, reach, leads, sales, can_end }] }
 * POST /marketing/campaigns/            { name, platform, objective, start_date, end_date, budget, description? }
 * PATCH /marketing/campaigns/<id>/      same fields (not sent = kept; the platform is fixed once numbers are entered)
 * POST /marketing/campaigns/<id>/end/
 *
 * GET  /marketing/posts/?status=scheduled&page_size=   ->  { count, results: [{ id, platform, scheduled_for, caption, campaign?, status, is_due, can_update }] }
 *      (scheduled includes posts whose time has passed: is_due, still to be posted and marked)
 * POST /marketing/posts/                { platform, scheduled_for, caption, campaign_id? }
 * POST /marketing/posts/<id>/status/    { status: 'published' | 'cancelled' }   (no platform connection: posted by hand, then marked)
 *
 * Numbers entered from each platform's analytics (they feed the dashboard). GET ?page=&search=&platform=&date_from=&date_to=
 * GET/POST /marketing/metrics/  · PATCH /marketing/metrics/<id>/   { date, platform, campaign_id?, reach, engagement,
 *                                                                    website_visitors, leads, sales_amount }  one per day + platform + campaign
 * GET/POST /marketing/content/  · PATCH /marketing/content/<id>/   { title, platform, published_on, views, likes, shares, url? }
 * GET/POST /marketing/audience-segments/ · PATCH .../<id>/         { platform, name, value (% of audience, 0-100), as_of }
 * Deleting: Super Admin only, DELETE /records/marketing_metric|content_item|audience_segment/<id>/
 */
export const marketingApi = {
  getOverview: ({ range }) => api.get('/marketing/overview/', clean({ range })),
  getPerformance: ({ days }) => api.get('/marketing/performance/', clean({ days })),
  getAudience: ({ platform }) => api.get('/marketing/audience/', clean({ platform })),
  getOptions: () => api.get('/marketing/options/'),
  listCampaigns: (params) => api.get('/marketing/campaigns/', clean(params)),
  createCampaign: (campaign) => api.post('/marketing/campaigns/', campaign),
  updateCampaign: (id, campaign) => api.patch(`/marketing/campaigns/${id}/`, campaign),
  endCampaign: (id) => api.post(`/marketing/campaigns/${id}/end/`),
  listPosts: (params) => api.get('/marketing/posts/', clean(params)),
  setPostStatus: (id, status) => api.post(`/marketing/posts/${id}/status/`, { status }),
  schedulePost: (post) => api.post('/marketing/posts/', post),
  listMetrics: (params) => api.get('/marketing/metrics/', clean(params)),
  saveMetric: (id, body) => (id ? api.patch(`/marketing/metrics/${id}/`, body) : api.post('/marketing/metrics/', body)),
  listContent: (params) => api.get('/marketing/content/', clean(params)),
  saveContent: (id, body) => (id ? api.patch(`/marketing/content/${id}/`, body) : api.post('/marketing/content/', body)),
  listSegments: (params) => api.get('/marketing/audience-segments/', clean(params)),
  saveSegment: (id, body) => (id ? api.patch(`/marketing/audience-segments/${id}/`, body) : api.post('/marketing/audience-segments/', body)),
}
