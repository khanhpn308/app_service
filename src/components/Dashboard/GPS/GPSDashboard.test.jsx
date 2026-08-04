import React from 'react'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
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
  default: ({ locationName, floorplanUrl, devices, getDeviceName }) => (
    <div data-testid="map-viewer">
      {locationName}|{floorplanUrl}|{devices.length}
      {devices.map((device) => (
        <span key={device.device_id} data-testid="map-device-label">
          {getDeviceName ? getDeviceName(device) : device.device_id}
        </span>
      ))}
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
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

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

  it('shows device identities without coordinates or per-device timestamps and searches by name or ID', async () => {
    const user = userEvent.setup()
    render(
      <GPSDashboard
        initialDevices={[
          {
            device_id: 662168,
            devicename: ' GPS3 ',
            location: 'FLOOR_1',
            x: 25,
            y: 44,
            ts_iso: '2026-08-02T15:28:10.000Z',
          },
          {
            device_id: 42,
            devicename: '   ',
            location: 'FLOOR_1',
            x: null,
            y: null,
            ts_iso: null,
          },
        ]}
      />,
    )

    await screen.findByText(/FLOOR_1\|blob:/)
    expect(screen.getByText('GPS3(662168)')).toBeTruthy()
    expect(screen.getAllByText('42')).toHaveLength(2)
    expect(screen.getAllByTestId('map-device-label')[0].textContent).toBe('GPS3')
    expect(screen.queryByText(/Tọa độ X/i)).toBeNull()
    expect(screen.queryByText(/Tọa độ Y/i)).toBeNull()
    expect(screen.queryByText('15:28:10')).toBeNull()

    const search = screen.getByPlaceholderText('Nhập tên hoặc mã thiết bị...')
    await user.type(search, 'gps3')
    expect(screen.getByText('GPS3(662168)')).toBeTruthy()
    expect(screen.queryByText('42')).toBeNull()

    await user.clear(search)
    await user.type(search, '42')
    expect(screen.getAllByText('42')).toHaveLength(2)
    expect(screen.queryByText('GPS3(662168)')).toBeNull()
  })

  it('shows one local dashboard clock that ticks every second and cleans up its interval', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 7, 2, 15, 37, 5))
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval')

    const { unmount } = render(<GPSDashboard />)

    expect(screen.getByLabelText('Thời gian hiện tại').textContent).toBe('15:37:05')
    expect(screen.queryByText('Live Tracking')).toBeNull()

    act(() => vi.advanceTimersByTime(1000))
    expect(screen.getByLabelText('Thời gian hiện tại').textContent).toBe('15:37:06')

    unmount()
    expect(clearIntervalSpy).toHaveBeenCalled()
  })
})
