/** Parameter + Value rows of a quality test (see components/ParameterRows). */
export const EMPTY_ROW = { parameter: '', value: '' }
const NUMBER = /^-?(\d+(\.\d+)?|\.\d+)$/ // 8, 8.5, -2.25, .5 (the server checks the same)

/** The first problem in the rows, or undefined. Nothing invalid is turned into 0. */
export function readingsError(rows) {
  const seen = new Set()
  for (const [i, r] of rows.entries()) {
    const name = r.parameter.trim()
    const value = String(r.value).trim()
    if (!name) return `Row ${i + 1}: enter the parameter name.`
    if (seen.has(name.toLowerCase())) return `Row ${i + 1}: ${name} is listed twice.`
    seen.add(name.toLowerCase())
    if (!value) return `Row ${i + 1}: enter the value.`
    if (!NUMBER.test(value)) return `Row ${i + 1}: the value must be a number, e.g. 8.5.`
  }
  return undefined
}

export const cleanReadings = (rows) => rows.map((r) => ({ parameter: r.parameter.trim(), value: String(r.value).trim() }))
