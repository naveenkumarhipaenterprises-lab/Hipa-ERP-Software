/** True when there is nothing meaningful to plot for the given value keys. */
export function isChartEmpty(data, keys) {
  if (!Array.isArray(data) || data.length === 0) return true
  return !data.some((row) => keys.some((k) => row?.[k] !== null && row?.[k] !== undefined && row[k] !== ''))
}
