import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  createAnchor,
  deleteAnchor,
  getAnchor,
  listLocationAnchors,
  manageAnchors,
  updateAnchor,
} from './anchorsApi'
import { apiFetch } from './api'

vi.mock('./api', () => ({ apiFetch: vi.fn() }))

describe('anchorsApi', () => {
  beforeEach(() => apiFetch.mockReset().mockResolvedValue({}))

  it('maps Anchor CRUD to the published REST contract', async () => {
    const signal = new AbortController().signal
    await listLocationAnchors(12, { signal })
    await createAnchor(12, { hardware_id: 'A-1', name: 'Alpha' })
    await getAnchor(31)
    await updateAnchor(31, { name: 'Beta' })
    await deleteAnchor(31)

    expect(apiFetch.mock.calls).toEqual([
      ['/api/locations/12/anchors', { signal }],
      ['/api/locations/12/anchors', { method: 'POST', body: JSON.stringify({ hardware_id: 'A-1', name: 'Alpha' }) }],
      ['/api/anchors/31'],
      ['/api/anchors/31', { method: 'PATCH', body: JSON.stringify({ name: 'Beta' }) }],
      ['/api/anchors/31', { method: 'DELETE' }],
    ])
  })

  it('encodes management filters and pagination', async () => {
    await manageAnchors({ q: 'A 1', groupId: 4, locationId: 12, limit: 25, offset: 50 })
    expect(apiFetch).toHaveBeenCalledWith(
      '/api/anchors/manage?q=A+1&group_id=4&location_id=12&limit=25&offset=50',
    )
  })
})
