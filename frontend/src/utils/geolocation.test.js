import { describe, expect, it, vi } from 'vitest'
import { LOCATION_MESSAGES, getDeviceLocation } from './geolocation'

const fix = { coords: { latitude: 11.341036, longitude: 77.717164, accuracy: 12.4 } }
const geoWith = (...results) => {
  const getCurrentPosition = vi.fn()
  results.forEach((r) => getCurrentPosition.mockImplementationOnce((ok, fail) => (r.coords ? ok(r) : fail(r))))
  return { getCurrentPosition }
}

describe('getDeviceLocation (attendance check-in / check-out)', () => {
  it('returns the position with a whole-metre accuracy, never a cached one', async () => {
    const geo = geoWith(fix)
    await expect(getDeviceLocation({ geo, secure: true })).resolves.toEqual({ latitude: 11.341036, longitude: 77.717164, accuracy: 12 })
    expect(geo.getCurrentPosition.mock.calls[0][2]).toMatchObject({ enableHighAccuracy: true, maximumAge: 0 })
  })
  it('explains a blocked permission and does not retry', async () => {
    const geo = geoWith({ code: 1 })
    await expect(getDeviceLocation({ geo, secure: true })).rejects.toThrow(LOCATION_MESSAGES.denied)
    expect(geo.getCurrentPosition).toHaveBeenCalledTimes(1)
  })
  it('falls back to a quicker position when GPS is too slow', async () => {
    const geo = geoWith({ code: 3 }, fix)
    await expect(getDeviceLocation({ geo, secure: true })).resolves.toMatchObject({ accuracy: 12 })
    expect(geo.getCurrentPosition.mock.calls[1][2]).toMatchObject({ enableHighAccuracy: false })
  })
  it('says why when it can never work', async () => {
    await expect(getDeviceLocation({ geo: geoWith(fix), secure: false })).rejects.toThrow(LOCATION_MESSAGES.insecure)
    await expect(getDeviceLocation({ geo: undefined, secure: true })).rejects.toThrow(LOCATION_MESSAGES.unsupported)
  })
})
