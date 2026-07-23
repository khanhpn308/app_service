import { describe, expect, it, vi } from 'vitest'

import { MAX_MAP_FILE_BYTES, validateMapFile } from './mapFileValidation'

const webp = (overrides = {}) =>
  new File(['map'], 'floor.webp', {
    type: 'image/webp',
    ...overrides,
  })

describe('validateMapFile', () => {
  it('accepts a WebP whose decoded width is exactly 800 px', async () => {
    const decode = vi.fn().mockResolvedValue({ width: 800, height: 1200 })

    await expect(validateMapFile(webp(), decode)).resolves.toEqual({
      width: 800,
      height: 1200,
    })
  })

  it.each([
    [new File(['map'], 'floor.png', { type: 'image/png' }), 'WebP'],
    [
      new File([new Uint8Array(MAX_MAP_FILE_BYTES + 1)], 'floor.webp', {
        type: 'image/webp',
      }),
      '5 MB',
    ],
  ])('rejects invalid file metadata', async (file, message) => {
    await expect(validateMapFile(file, vi.fn())).rejects.toThrow(message)
  })

  it.each([
    [{ width: 799, height: 600 }, '800'],
    [{ width: 800, height: 8001 }, 'chiều cao'],
  ])('rejects invalid decoded dimensions', async (dimensions, message) => {
    await expect(
      validateMapFile(webp(), vi.fn().mockResolvedValue(dimensions)),
    ).rejects.toThrow(message)
  })
})
