import axios from 'axios'

const TOKEN_KEY = 'hipa_token'
const USER_KEY = 'hipa_user'

/** Token lives in localStorage when "Remember me" is ticked, otherwise sessionStorage. */
export const tokenStorage = {
  get: () => localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY),
  getUser: () => {
    const raw = localStorage.getItem(USER_KEY) || sessionStorage.getItem(USER_KEY)
    try {
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  },
  set: (token, user, remember) => {
    const store = remember ? localStorage : sessionStorage
    tokenStorage.clear()
    store.setItem(TOKEN_KEY, token)
    store.setItem(USER_KEY, JSON.stringify(user))
  },
  /** Swaps in a new token where the current one is kept (e.g. after a password change). */
  replace: (token) => {
    const store = localStorage.getItem(TOKEN_KEY) ? localStorage : sessionStorage
    store.setItem(TOKEN_KEY, token)
  },
  clear: () => {
    for (const s of [localStorage, sessionStorage]) {
      s.removeItem(TOKEN_KEY)
      s.removeItem(USER_KEY)
    }
  },
}

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 20000,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.request.use((config) => {
  const token = tokenStorage.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    // Only a rejected *existing* session counts as expiry; a failed login is just a 401
    if (error.response?.status === 401 && tokenStorage.get()) {
      tokenStorage.clear()
      window.dispatchEvent(new Event('auth:logout'))
    }
    return Promise.reject(toApiError(error))
  },
)

/** Turns axios / DRF errors into one readable message. */
const UNREACHABLE = 'Cannot reach the server. Please check that the HIPA MASALA backend is running and try again.'
const FALLBACK = 'Something went wrong. Please try again.'

function toApiError(error) {
  const status = error.response?.status
  const data = error.response?.data
  let message = FALLBACK
  // No response, or a gateway error from the dev proxy / web server = backend down
  if (!error.response || [502, 503, 504].includes(status)) message = UNREACHABLE
  else if (data instanceof Blob) message = status === 404 ? 'This file is not available yet.' : FALLBACK
  else if (typeof data === 'string' && data.trim() && data.length < 200) message = data.trim()
  else if (data?.detail) message = String(data.detail)
  else if (data && typeof data === 'object') {
    const first = Object.values(data)[0]
    if (Array.isArray(first) && first[0]) message = String(first[0])
    else if (typeof first === 'string' && first) message = first
  }
  const err = new Error(message || FALLBACK)
  err.status = error.response?.status
  err.fields = data && typeof data === 'object' && !(data instanceof Blob) ? data : undefined
  return err
}

/** Drops empty filters so the backend never receives `search=` etc. */
export const cleanParams = (params) =>
  Object.fromEntries(Object.entries(params ?? {}).filter(([, v]) => v !== '' && v !== null && v !== undefined))

/**
 * Thin wrappers that return the response body. Every call goes to the real
 * Django API; if it is unreachable the promise rejects and the UI shows an
 * error state. There is no fallback data.
 */
export const api = {
  get: async (url, params) => (await client.get(url, { params })).data,
  post: async (url, body) => (await client.post(url, body)).data,
  put: async (url, body) => (await client.put(url, body)).data,
  patch: async (url, body) => (await client.patch(url, body)).data,
  delete: async (url) => (await client.delete(url)).data,
  /** Sends a file as multipart/form-data (e.g. CSV imports), with optional extra form fields. */
  upload: async (url, file, field = 'file', extra = {}) => {
    const form = new FormData()
    form.append(field, file)
    for (const [k, v] of Object.entries(cleanParams(extra))) form.append(k, typeof v === 'boolean' ? String(v) : v)
    return (await client.post(url, form, { headers: { 'Content-Type': 'multipart/form-data' } })).data
  },
  /** Fetches a generated file (e.g. a quotation PDF) as a Blob, for previewing or printing in the browser. */
  blob: async (url, params) => (await client.get(url, { params, responseType: 'blob' })).data,
  /** Saves a file the backend generates (reports, exports). Uses the server's filename when it sends one. */
  download: async (url, params, fallbackName) => {
    const res = await client.get(url, { params, responseType: 'blob' })
    const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(res.headers['content-disposition'] ?? '')
    const name = match ? decodeURIComponent(match[1]) : fallbackName
    const href = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = href
    a.download = name
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(href), 1000)
    return name
  },
}

export default client
