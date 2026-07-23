import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  deleteMap,
  fetchMapImage,
  listDeletedMaps,
  listGroupMaps,
  uploadGroupMap,
} from './mapsApi'

describe('mapsApi', () => {
  beforeEach(() => {
    localStorage.setItem('iot_token', 'test-token')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((path) => {
        if (String(path).endsWith('/image')) {
          return Promise.resolve(
            new Response(new Blob(['map'], { type: 'image/webp' }), {
              status: 200,
              headers: { 'Content-Type': 'image/webp' },
            }),
          )
        }
        return Promise.resolve(
          new Response(path.includes('deleted-maps') ? '{"data":[]}' : '[]', {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }),
    )
  })

  it('uses map REST paths and leaves the multipart boundary to the browser', async () => {
    const file = new File(['map'], 'floor.webp', { type: 'image/webp' })

    await listGroupMaps(7)
    await uploadGroupMap(7, { location: 'FLOOR_1', file })
    await deleteMap(12)
    await listDeletedMaps({ limit: 25, offset: 50 })

    expect(
      fetch.mock.calls.map(([path]) => new URL(path, 'http://local').pathname +
        new URL(path, 'http://local').search),
    ).toEqual([
      '/api/map-groups/7/maps',
      '/api/map-groups/7/maps',
      '/api/maps/12',
      '/api/admin/deleted-maps?limit=25&offset=50',
    ])
    const uploadOptions = fetch.mock.calls[1][1]
    expect(uploadOptions.method).toBe('POST')
    expect(uploadOptions.body).toBeInstanceOf(FormData)
    expect(uploadOptions.body.get('location')).toBe('FLOOR_1')
    expect(uploadOptions.body.get('file')).toBe(file)
    expect(uploadOptions.headers['Content-Type']).toBeUndefined()
    expect(uploadOptions.headers.Authorization).toBe('Bearer test-token')
  })

  it('returns an authenticated image Blob without parsing it as JSON', async () => {
    const blob = await fetchMapImage(12)

    expect(blob).toBeInstanceOf(Blob)
    expect(blob.type).toBe('image/webp')
    expect(fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/maps\/12\/image$/),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
      }),
    )
  })
})
