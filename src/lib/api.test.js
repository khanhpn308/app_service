import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from './api'

describe('apiFetch errors', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('preserves the HTTP status for permission-revocation handling', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'Forbidden' }),
      { status: 403, statusText: 'Forbidden', headers: { 'Content-Type': 'application/json' } },
    )))

    await expect(apiFetch('/api/anchors/31')).rejects.toMatchObject({
      message: 'Forbidden',
      status: 403,
    })
  })
})
