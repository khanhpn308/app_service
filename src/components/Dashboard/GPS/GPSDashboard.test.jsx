import React from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import GPSDashboard from './GPSDashboard'
import { listMapGroups } from '../../../lib/mapGroupsApi'
import {
  deleteMap,
  fetchMapImage,
  listGroupMaps,
} from '../../../lib/mapsApi'

vi.mock('../../../lib/mapGroupsApi', () => ({
  listMapGroups: vi.fn(),
}))

vi.mock('../../../lib/mapsApi', () => ({
  deleteMap: vi.fn(),
  fetchMapImage: vi.fn(),
  listGroupMaps: vi.fn(),
}))

vi.mock('./MapViewer', () => ({
  default: ({ locationName, floorplanUrl, devices }) => (
    <div data-testid="map-viewer">
      {locationName}|{floorplanUrl}|{devices.length}
    </div>
  ),
}))

vi.mock('./MapGroupManagerDialog', () => ({
  default: () => <button type="button">Quản lý nhóm</button>,
}))

vi.mock('./UploadMapDialog', () => ({
  default: () => <button type="button">Thêm bản đồ</button>,
}))

const groups = [
  { group_id: 1, name: 'Nhà máy A', can_manage: true },
  { group_id: 2, name: 'Nhóm chia sẻ', can_manage: false },
]
const mapsByGroup = {
  1: [
    { location_id: 10, location: 'FLOOR_1', group_id: 1 },
    { location_id: 11, location: 'FLOOR_2', group_id: 1 },
  ],
  2: [{ location_id: 20, location: 'WAREHOUSE', group_id: 2 }],
}

describe('GPSDashboard map catalog', () => {
  afterEach(cleanup)

  beforeEach(() => {
    listMapGroups.mockResolvedValue(groups)
    listGroupMaps.mockImplementation((groupId) =>
      Promise.resolve(mapsByGroup[groupId] || []),
    )
    fetchMapImage.mockImplementation((mapId) =>
      Promise.resolve(new Blob([String(mapId)], { type: 'image/webp' })),
    )
    deleteMap.mockResolvedValue(null)
    vi.spyOn(URL, 'createObjectURL').mockImplementation(
      (blob) => `blob:${blob.size}`,
    )
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  })

  it('loads only the selected MySQL map and keeps payload matching by location', async () => {
    const user = userEvent.setup()
    render(
      <GPSDashboard
        initialDevices={[
          { device_id: 'A', location: ' floor_1 ', x: 1, y: 2 },
          { device_id: 'B', location: 'FLOOR_2', x: 3, y: 4 },
        ]}
      />,
    )

    expect(await screen.findByText(/FLOOR_1\|blob:/)).toBeTruthy()
    expect(screen.getByTestId('map-viewer').textContent).toContain('|1')
    expect(fetchMapImage).toHaveBeenCalledTimes(1)
    expect(fetchMapImage).toHaveBeenCalledWith(10)

    await user.selectOptions(screen.getByLabelText('Khu vực (Map)'), '11')
    await waitFor(() => expect(fetchMapImage).toHaveBeenCalledWith(11))
    expect(screen.getByTestId('map-viewer').textContent).toContain('FLOOR_2')
    expect(screen.getByTestId('map-viewer').textContent).toContain('|1')

    await user.selectOptions(screen.getByLabelText('Nhóm bản đồ'), '2')
    await waitFor(() => expect(listGroupMaps).toHaveBeenCalledWith(2))
    expect(await screen.findByText(/WAREHOUSE\|blob:/)).toBeTruthy()
  })

  it('allows a manager to archive the selected map', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const user = userEvent.setup()
    render(<GPSDashboard />)

    await screen.findByText(/FLOOR_1\|blob:/)
    await user.click(screen.getByRole('button', { name: 'Xóa bản đồ' }))

    await waitFor(() => expect(deleteMap).toHaveBeenCalledWith(10))
    expect(listGroupMaps).toHaveBeenCalledTimes(2)
  })
})
