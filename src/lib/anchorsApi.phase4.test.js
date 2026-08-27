import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getAnchorConfigStatus, resyncAnchorConfig } from './anchorsApi'
import { apiFetch } from './api'

vi.mock('./api', () => ({ apiFetch: vi.fn() }))

beforeEach(() => apiFetch.mockReset())

describe('Anchor sync API', () => {
  it('uses the status and resync contracts', async () => {
    await getAnchorConfigStatus(12)
    expect(apiFetch).toHaveBeenCalledWith('/api/locations/12/anchor-config-status')
    await resyncAnchorConfig(12, 101)
    expect(apiFetch).toHaveBeenLastCalledWith('/api/locations/12/gateways/101/anchor-config-resync', { method: 'POST' })
  })
})
