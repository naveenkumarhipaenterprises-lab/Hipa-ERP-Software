import { api } from './client'

/** DELETE /records/<kind>/<id>/ : Super Admin only. The server undoes the entry's stock and money effects. */
export const recordsApi = {
  remove: (kind, id) => api.delete(`/records/${kind}/${id}/`),
}
