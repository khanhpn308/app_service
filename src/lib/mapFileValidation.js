export const MAX_MAP_FILE_BYTES = 5 * 1024 * 1024

async function decodeImageDimensions(file) {
  if (typeof createImageBitmap === 'function') {
    const bitmap = await createImageBitmap(file)
    const result = { width: bitmap.width, height: bitmap.height }
    bitmap.close()
    return result
  }

  const objectUrl = URL.createObjectURL(file)
  try {
    return await new Promise((resolve, reject) => {
      const image = new Image()
      image.onload = () =>
        resolve({ width: image.naturalWidth, height: image.naturalHeight })
      image.onerror = () => reject(new Error('Không thể đọc kích thước ảnh WebP.'))
      image.src = objectUrl
    })
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}

export async function validateMapFile(file, decode = decodeImageDimensions) {
  if (!file) {
    throw new Error('Vui lòng chọn ảnh WebP.')
  }
  if (
    file.type !== 'image/webp' ||
    !String(file.name || '').toLowerCase().endsWith('.webp')
  ) {
    throw new Error('Ảnh phải đúng định dạng WebP.')
  }
  if (file.size < 1 || file.size > MAX_MAP_FILE_BYTES) {
    throw new Error('Ảnh phải có dung lượng từ 1 byte đến tối đa 5 MB.')
  }

  const dimensions = await decode(file)
  if (dimensions.width !== 800) {
    throw new Error('Chiều rộng ảnh phải đúng 800 px.')
  }
  if (dimensions.height < 1 || dimensions.height > 8000) {
    throw new Error('Ảnh phải có chiều cao từ 1 đến 8000 px.')
  }
  return dimensions
}
