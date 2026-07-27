export const MAX_MAP_FILE_BYTES = 10 * 1024 * 1024

const EXTENSION_TO_MIME_TYPE = {
  webp: 'image/webp',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
}

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
      image.onerror = () => reject(new Error('Không thể đọc nội dung ảnh.'))
      image.src = objectUrl
    })
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}

export async function validateMapFile(file, decode = decodeImageDimensions) {
  if (!file) {
    throw new Error('Vui lòng chọn ảnh WebP, PNG hoặc JPG.')
  }

  const filename = String(file.name || '').toLowerCase()
  const extension = filename.includes('.') ? filename.split('.').pop() : ''
  const expectedMimeType = EXTENSION_TO_MIME_TYPE[extension]
  const supportedMimeTypes = Object.values(EXTENSION_TO_MIME_TYPE)
  if (!expectedMimeType || !supportedMimeTypes.includes(file.type)) {
    throw new Error('Ảnh phải đúng định dạng WebP, PNG hoặc JPG.')
  }
  if (file.type !== expectedMimeType) {
    throw new Error('Đuôi file và định dạng ảnh phải khớp nhau.')
  }
  if (file.size < 1 || file.size >= MAX_MAP_FILE_BYTES) {
    throw new Error('Ảnh phải có dung lượng từ 1 byte và nhỏ hơn 10 MB.')
  }

  const dimensions = await decode(file)
  if (dimensions.width < 1 || dimensions.height < 1) {
    throw new Error('Không thể đọc kích thước ảnh hợp lệ.')
  }
  return dimensions
}
