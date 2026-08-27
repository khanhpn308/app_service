import { apiFetch } from './api'

export function listLocationAnchors(locationId, { signal } = {}) {
  return apiFetch(`/api/locations/${locationId}/anchors`, signal ? { signal } : {})
}

export function createAnchor(locationId, payload) {
  return apiFetch(`/api/locations/${locationId}/anchors`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getAnchor(anchorId) {
  return apiFetch(`/api/anchors/${anchorId}`)
}

export function updateAnchor(anchorId, payload) {
  return apiFetch(`/api/anchors/${anchorId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteAnchor(anchorId) {
  return apiFetch(`/api/anchors/${anchorId}`, { method: 'DELETE' })
}

export function manageAnchors({ q, groupId, locationId, limit, offset } = {}, { signal } = {}) {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  if (groupId != null) params.set('group_id', groupId)
  if (locationId != null) params.set('location_id', locationId)
  if (limit != null) params.set('limit', limit)
  if (offset != null) params.set('offset', offset)
  const query = params.toString()
  const path = `/api/anchors/manage${query ? `?${query}` : ''}`
  return signal ? apiFetch(path, { signal }) : apiFetch(path)
}

export function getAnchorConfigStatus(locationId, { signal } = {}) {
  const path = `/api/locations/${locationId}/anchor-config-status`
  return signal ? apiFetch(path, { signal }) : apiFetch(path)
}

export function resyncAnchorConfig(locationId, gatewayId) {
  return apiFetch(`/api/locations/${locationId}/gateways/${gatewayId}/anchor-config-resync`, { method: 'POST' })
}
