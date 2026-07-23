import React from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import UploadMapDialog from './UploadMapDialog'
import { uploadGroupMap } from '../../../lib/mapsApi'
import { validateMapFile } from '../../../lib/mapFileValidation'

vi.mock('../../../lib/mapsApi', () => ({
  uploadGroupMap: vi.fn(),
}))

vi.mock('../../../lib/mapFileValidation', () => ({
  validateMapFile: vi.fn(),
}))

const groups = [
  { group_id: 1, name: 'Nhà máy A', can_manage: true },
  { group_id: 2, name: 'Được chia sẻ', can_manage: false },
]

describe('UploadMapDialog', () => {
  afterEach(cleanup)

  beforeEach(() => {
    validateMapFile.mockResolvedValue({ width: 800, height: 600 })
    uploadGroupMap.mockResolvedValue({
      location_id: 9,
      location: 'FLOOR_1',
      group_id: 1,
    })
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:preview')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  })

  it('uploads a validated WebP into a group the user can manage', async () => {
    const onUploaded = vi.fn()
    const user = userEvent.setup()
    render(
      <UploadMapDialog
        groups={groups}
        defaultGroupId={1}
        onUploaded={onUploaded}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Thêm bản đồ' }))
    expect(screen.getByText('WebP tĩnh · 800×1–8000 px · tối đa 5 MB')).toBeTruthy()
    expect(screen.queryByRole('option', { name: 'Được chia sẻ' })).toBeNull()

    await user.type(screen.getByLabelText('Location gateway'), ' FLOOR_1 ')
    const file = new File(['map'], 'floor.webp', { type: 'image/webp' })
    await user.upload(screen.getByLabelText('Chọn ảnh WebP'), file)
    await user.click(screen.getByRole('button', { name: 'Tải ảnh lên' }))

    await waitFor(() => {
      expect(validateMapFile).toHaveBeenCalledWith(file)
      expect(uploadGroupMap).toHaveBeenCalledWith(1, {
        location: 'FLOOR_1',
        file,
      })
      expect(onUploaded).toHaveBeenCalledWith(
        expect.objectContaining({ location_id: 9 }),
      )
    })
  })

  it('shows client validation failures without sending a request', async () => {
    validateMapFile.mockRejectedValueOnce(new Error('Chiều rộng ảnh phải đúng 800 px.'))
    const user = userEvent.setup()
    render(<UploadMapDialog groups={groups} defaultGroupId={1} />)

    await user.click(screen.getByRole('button', { name: 'Thêm bản đồ' }))
    await user.type(screen.getByLabelText('Location gateway'), 'FLOOR_2')
    await user.upload(
      screen.getByLabelText('Chọn ảnh WebP'),
      new File(['map'], 'floor.webp', { type: 'image/webp' }),
    )

    expect((await screen.findByRole('alert')).textContent).toContain('800 px')
    expect(uploadGroupMap).not.toHaveBeenCalled()
  })

  it('keeps the dialog open and shows the backend upload error', async () => {
    uploadGroupMap.mockRejectedValueOnce(
      new Error('Location đang được sử dụng bởi bản đồ khác.'),
    )
    const user = userEvent.setup()
    render(<UploadMapDialog groups={groups} defaultGroupId={1} />)

    await user.click(screen.getByRole('button', { name: 'Thêm bản đồ' }))
    await user.type(screen.getByLabelText('Location gateway'), 'FLOOR_DUPLICATE')
    await user.upload(
      screen.getByLabelText('Chọn ảnh WebP'),
      new File(['map'], 'floor.webp', { type: 'image/webp' }),
    )
    await user.click(screen.getByRole('button', { name: 'Tải ảnh lên' }))

    expect((await screen.findByRole('alert')).textContent).toContain(
      'Location đang được sử dụng',
    )
    expect(screen.getByRole('dialog')).toBeTruthy()
  })
})
