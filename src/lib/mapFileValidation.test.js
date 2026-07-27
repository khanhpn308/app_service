import { describe, expect, it, vi } from 'vitest'

import { MAX_MAP_FILE_BYTES, validateMapFile } from './mapFileValidation'

const imageFile = (name, type, content = ['map']) =>
  new File(content, name, { type })

describe('validateMapFile', () => {
  it.each([
    ['floor.webp', 'image/webp'],
    ['floor.png', 'image/png'],
    ['floor.jpg', 'image/jpeg'],
    ['floor.jpeg', 'image/jpeg'],
  ])('accepts supported static image metadata: %s', async (name, type) => {
    const decode = vi.fn().mockResolvedValue({ width: 1234, height: 9001 })
    const file = imageFile(name, type)

    await expect(validateMapFile(file, decode)).resolves.toEqual({
      width: 1234,
      height: 9001,
    })
    expect(decode).toHaveBeenCalledWith(file)
  })

  it.each([
    [imageFile('floor.gif', 'image/gif'), 'WebP, PNG hoặc JPG'],
    [imageFile('floor.webp', 'image/png'), 'khớp'],
    [
      imageFile(
        'floor.png',
        'image/png',
        [new Uint8Array(MAX_MAP_FILE_BYTES)],
      ),
      '10 MB',
    ],
  ])('rejects invalid file metadata', async (file, message) => {
    await expect(validateMapFile(file, vi.fn())).rejects.toThrow(message)
  })

  it('does not impose a width or height limit', async () => {
    await expect(
      validateMapFile(
        imageFile('floor.png', 'image/png'),
        vi.fn().mockResolvedValue({ width: 1, height: 25000 }),
      ),
    ).resolves.toEqual({ width: 1, height: 25000 })
  })
})
