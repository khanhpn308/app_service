import { apiFetch, apiFetchBlob } from './api'

export function listGroupMaps(groupId) {
  return apiFetch(`/api/map-groups/${groupId}/maps`)
}

export function uploadGroupMap(groupId, { location, file }) {
  const body = new FormData()
  body.append('location', location)
  body.append('file', file)
  return apiFetch(`/api/map-groups/${groupId}/maps`, {
    method: 'POST',
    body,
  })
}

export function fetchMapImage(mapId) {
  return apiFetchBlob(`/api/maps/${mapId}/image`)
}

export function deleteMap(mapId) {
  return apiFetch(`/api/maps/${mapId}`, { method: 'DELETE' })
}

export function listDeletedMaps({ limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })
  return apiFetch(`/api/admin/deleted-maps?${params}`)
}
