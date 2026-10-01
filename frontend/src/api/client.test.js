import { AxiosError } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import client, { api, cleanParams, tokenStorage } from './client'

// Replaces axios's network layer inside these tests only: nothing leaves the test process
let respond
const realAdapter = client.defaults.adapter
beforeEach(() => {
  client.defaults.adapter = async (config) => respond(config)
})
afterEach(() => {
  client.defaults.adapter = realAdapter
})

const reply = (status, data, config) => {
  const response = { status, data, statusText: '', headers: {}, config }
  if (status >= 400) throw new AxiosError('failed', 'ERR_BAD_RESPONSE', config, null, response)
  return response
}

describe('api client', () => {
  it('returns the response body and sends the stored token', async () => {
    tokenStorage.set('abc123', { id: 1, role: 'admin' }, false)
    let sentAuth
    respond = (config) => {
      sentAuth = config.headers.Authorization
      return reply(200, { ok: true }, config)
    }
    await expect(api.get('/x/')).resolves.toEqual({ ok: true })
    expect(sentAuth).toBe('Bearer abc123')
  })

  it('reports an unreachable backend clearly (no response, or a 502 from the dev proxy)', async () => {
    respond = (config) => {
      throw new AxiosError('Network Error', 'ERR_NETWORK', config)
    }
    await expect(api.get('/x/')).rejects.toThrow(/Cannot reach the server/)
    respond = (config) => reply(502, '', config)
    await expect(api.get('/x/')).rejects.toThrow(/Cannot reach the server/)
  })

  it('uses the DRF "detail" message, or the first field error, and keeps the field errors', async () => {
    respond = (config) => reply(400, { detail: 'Not allowed' }, config)
    await expect(api.post('/x/', {})).rejects.toThrow('Not allowed')

    respond = (config) => reply(400, { quantity_kg: ['Exceeds available stock'] }, config)
    const err = await api.post('/x/', {}).catch((e) => e)
    expect(err.message).toBe('Exceeds available stock')
    expect(err.status).toBe(400)
    expect(err.fields).toEqual({ quantity_kg: ['Exceeds available stock'] })
  })

  it('ends the session when the server rejects a stored token (401)', async () => {
    tokenStorage.set('expired', { id: 1 }, true)
    const onLogout = vi.fn()
    window.addEventListener('auth:logout', onLogout)
    respond = (config) => reply(401, { detail: 'Token expired' }, config)
    await api.get('/x/').catch(() => {})
    window.removeEventListener('auth:logout', onLogout)
    expect(onLogout).toHaveBeenCalledOnce()
    expect(tokenStorage.get()).toBeNull()
  })

  it('does not treat a wrong password (401 with no stored token) as an expired session', async () => {
    const onLogout = vi.fn()
    window.addEventListener('auth:logout', onLogout)
    respond = (config) => reply(401, { detail: 'No active account' }, config)
    await api.post('/auth/login/', {}).catch(() => {})
    window.removeEventListener('auth:logout', onLogout)
    expect(onLogout).not.toHaveBeenCalled()
  })
})

describe('tokenStorage', () => {
  it('uses localStorage only when "remember me" is ticked', () => {
    tokenStorage.set('t1', { id: 1 }, false)
    expect(sessionStorage.getItem('hipa_token')).toBe('t1')
    expect(localStorage.getItem('hipa_token')).toBeNull()
    tokenStorage.set('t2', { id: 1 }, true)
    expect(localStorage.getItem('hipa_token')).toBe('t2')
    expect(sessionStorage.getItem('hipa_token')).toBeNull()
  })
  it('survives a corrupted stored user', () => {
    sessionStorage.setItem('hipa_user', '{not json')
    expect(tokenStorage.getUser()).toBeNull()
  })
})

describe('cleanParams', () => {
  it('drops empty filters but keeps zero and false', () => {
    expect(cleanParams({ a: '', b: null, c: undefined, d: 0, e: false, f: 'x' })).toEqual({ d: 0, e: false, f: 'x' })
  })
})
