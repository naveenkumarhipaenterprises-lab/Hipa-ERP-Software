/**
 * The device's GPS position for attendance check-in / check-out. Phones use GPS; laptops and desktops use Wi-Fi
 * positioning, which is less exact (the accuracy in metres says how far off it may be). Browsers only share the
 * location over HTTPS (or localhost) and only after the user allows it.
 */
export const LOCATION_MESSAGES = {
  insecure: 'Location only works over a secure (https://) connection. Open the portal from its https:// address.',
  unsupported: "This device or browser can't share its location. Use a phone or a recent version of Chrome, Edge or Safari.",
  denied: 'Location access is blocked. Allow location for this portal in your browser or phone settings, then try again.',
  unavailable: "Your location couldn't be found. Turn on GPS / location services and try again.",
  timeout: 'Finding your location took too long. Check that location is turned on, move near a window or outdoors, and try again.',
}

function locationError(code) {
  const err = new Error(LOCATION_MESSAGES[code])
  err.code = code
  return err
}

const ERROR_CODES = { 1: 'denied', 2: 'unavailable', 3: 'timeout' }

function position(geo, options) {
  return new Promise((resolve, reject) => {
    geo.getCurrentPosition(
      (p) => resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude, accuracy: Math.round(p.coords.accuracy) }),
      (e) => reject(locationError(ERROR_CODES[e?.code] ?? 'unavailable')),
      options,
    )
  })
}

/**
 * { latitude, longitude, accuracy } of this device, asked fresh every time (never a cached position).
 * If an exact GPS fix takes too long, tries once more with a quicker network position.
 */
export async function getDeviceLocation({ geo = globalThis.navigator?.geolocation, secure = globalThis.isSecureContext } = {}) {
  if (secure === false) throw locationError('insecure')
  if (!geo?.getCurrentPosition) throw locationError('unsupported')
  try {
    return await position(geo, { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 })
  } catch (err) {
    if (err.code !== 'timeout' && err.code !== 'unavailable') throw err
    return position(geo, { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 })
  }
}
