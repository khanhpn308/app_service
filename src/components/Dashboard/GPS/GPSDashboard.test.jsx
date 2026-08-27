import React from 'react'
import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import GPSDashboard from './GPSDashboard'
import { createAnchor, listLocationAnchors, updateAnchor } from '../../../lib/anchorsApi'
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

vi.mock('../../../lib/anchorsApi', () => ({
  createAnchor: vi.fn(),
  deleteAnchor: vi.fn(),
  listLocationAnchors: vi.fn(),
  updateAnchor: vi.fn(),
}))

const authState = vi.hoisted(() => ({
  user: { user_id: 1, role: 'admin', can_config_anchor: 'yes' },
  refreshUser: vi.fn(),
}))

vi.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => authState,
}))

vi.mock('./MapViewer', () => ({
  default: ({ locationName, floorplanUrl, devices, anchors = [], canConfigureAnchors, onAnchorClick, getDeviceName }) => (
    <div data-testid="map-viewer">
      {locationName}|{floorplanUrl}|{devices.length}
      {devices.map((device) => (
        <span key={device.device_id} data-testid="map-device-label">
          {getDeviceName ? getDeviceName(device) : device.device_id}
        </span>
      ))}
      <span data-testid="anchor-count">{anchors.length}</span>
      {anchors.map((anchor) => canConfigureAnchors
        ? <button type="button" key={anchor.anchor_id} onClick={() => onAnchorClick(anchor)}>Anchor {anchor.name}</button>
        : <span key={anchor.anchor_id}>Anchor {anchor.name}</span>)}
    </div>
  ),
}))

vi.mock('./MapGroupManagerDialog', () => ({
  default: () => <button type="button">Quản lý nhóm</button>,
}))

const catalogAnchor = {
  anchor_id: 88,
  mac_address: '12:21:AA:43:1A:88',
  hardware_id: 'CAT:88',
  name: 'Catalog stale',
  group_id: 2,
  location_id: 20,
  location: 'WAREHOUSE',
  x: 15,
  y: 25,
  z: 0,
}

vi.mock('./AnchorManagerDialog', () => ({
  default: ({ onSelect }) => (
    <button type="button" onClick={() => onSelect(catalogAnchor)}>Quản lý Anchor</button>
  ),
}))

vi.mock('./UploadMapDialog', () => ({
  default: () => <button type="button">Thêm bản đồ</button>,
}))

const groups = [
  { group_id: 1, name: 'Nhà máy A', can_manage: true, access_role: 'owner' },
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
    listLocationAnchors.mockResolvedValue([])
    createAnchor.mockResolvedValue({ data: { anchor_id: 31, mac_address: '12:21:AA:43:1A:31', hardware_id: 'AA:01', name: 'Alpha', x: 50, y: 50, z: 0 } })
    updateAnchor.mockResolvedValue({ data: { anchor_id: 31, mac_address: '12:21:AA:43:1A:31', hardware_id: 'AA:01', name: 'Beta', x: 50, y: 50, z: 0 } })
    authState.user = { user_id: 1, role: 'admin', can_config_anchor: 'yes' }
    authState.refreshUser.mockReset().mockResolvedValue(undefined)
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

  it('groups map actions in a vertical toolbar', async () => {
    render(<GPSDashboard />)

    await screen.findByText(/FLOOR_1\|blob:/)
    const toolbar = screen.getByRole('toolbar', { name: 'Thao tác bản đồ' })

    expect(toolbar.getAttribute('aria-orientation')).toBe('vertical')
    expect(within(toolbar).getAllByRole('button').map((button) => button.textContent.trim()))
      .toEqual([
        'Thêm bản đồ',
        'Thêm Anchor',
        'Quản lý Anchor',
        'Đang chờ',
        'Xóa bản đồ',
        'Quản lý nhóm',
      ])
  })

  it('organizes the workspace into system, map, and device regions', async () => {
    render(<GPSDashboard />)

    await screen.findByText(/FLOOR_1\|blob:/)

    const systemPanel = screen.getByRole('complementary', { name: 'Hệ thống' })
    const mapWorkspace = screen.getByRole('region', { name: 'Không gian bản đồ' })
    const devicePanel = screen.getByRole('complementary', { name: 'Thiết bị hiển thị' })

    expect(systemPanel.compareDocumentPosition(mapWorkspace) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(mapWorkspace.compareDocumentPosition(devicePanel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(within(mapWorkspace).getByRole('toolbar', { name: 'Bộ lọc bản đồ' })).toBeTruthy()
    const mapSurface = within(mapWorkspace).getByTestId('map-surface')
    expect(mapSurface.style.backgroundImage).toBe('')
    expect(mapSurface.className).toContain('overflow-hidden')
  })

  it('exposes the system controls in an accessible mobile drawer', async () => {
    const user = userEvent.setup()
    render(<GPSDashboard />)

    await screen.findByText(/FLOOR_1\|blob:/)
    await user.click(screen.getByRole('button', { name: 'Hệ thống' }))

    const drawer = await screen.findByRole('dialog', { name: 'Hệ thống' })
    expect(within(drawer).getByRole('toolbar', { name: 'Thao tác bản đồ' })).toBeTruthy()
    expect(within(drawer).getByRole('button', { name: 'Thêm bản đồ' })).toBeTruthy()
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

  it('clears stale anchors and aborts their request when the selected map changes', async () => {
    const user = userEvent.setup()
    let resolveFirst
    listLocationAnchors
      .mockImplementationOnce((_id, { signal }) => new Promise((resolve) => {
        resolveFirst = () => resolve([{ anchor_id: 1, name: 'Old', x: 1, y: 1 }])
        signal.addEventListener('abort', () => resolve([]))
      }))
      .mockResolvedValueOnce([{ anchor_id: 2, name: 'New', x: 2, y: 2 }])

    render(<GPSDashboard />)
    await screen.findByText(/FLOOR_1\|blob:/)
    const firstSignal = listLocationAnchors.mock.calls[0][1].signal
    await user.selectOptions(screen.getByLabelText('Khu vực (Map)'), '11')
    await screen.findByRole('button', { name: 'Anchor New' })

    expect(firstSignal.aborted).toBe(true)
    resolveFirst()
    expect(screen.queryByText('Anchor Old')).toBeNull()
  })

  it('creates from a 50:50 draft and only exposes config controls to admin or owner with the flag', async () => {
    const user = userEvent.setup()
    authState.user = { user_id: 7, role: 'user', can_config_anchor: 'yes' }
    render(<GPSDashboard />)
    await screen.findByText(/FLOOR_1\|blob:/)

    await user.click(screen.getByRole('button', { name: 'Thêm Anchor' }))
    expect(screen.getByLabelText('Tọa độ X').value).toBe('50')
    expect(screen.getByLabelText('Tọa độ Y').value).toBe('50')
    await user.type(screen.getByLabelText('MAC Address'), '12:21:aa:43:1a:31')
    await user.type(screen.getByLabelText('Tên Anchor'), 'Alpha')
    await user.click(screen.getByRole('button', { name: 'Lưu Anchor' }))

    await waitFor(() => expect(createAnchor).toHaveBeenCalledTimes(1))
    expect(createAnchor).toHaveBeenCalledWith(10, {
      mac_address: '12:21:AA:43:1A:31', name: 'Alpha', x: 50, y: 50, z: 0,
    })
  })

  it('closes the editor, refreshes the session and hides controls after a mutation 403', async () => {
    const user = userEvent.setup()
    const forbidden = Object.assign(new Error('Forbidden'), { status: 403 })
    listLocationAnchors.mockResolvedValue([{ anchor_id: 31, mac_address: '12:21:AA:43:1A:31', hardware_id: 'AA:01', name: 'Alpha', x: 50, y: 50, z: 0 }])
    updateAnchor.mockRejectedValue(forbidden)
    render(<GPSDashboard />)

    await user.click(await screen.findByRole('button', { name: 'Anchor Alpha' }))
    await user.clear(screen.getByLabelText('Tên Anchor'))
    await user.type(screen.getByLabelText('Tên Anchor'), 'Beta')
    await user.click(screen.getByRole('button', { name: 'Lưu Anchor' }))

    await waitFor(() => expect(authState.refreshUser).toHaveBeenCalledTimes(1))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Thêm Anchor' })).toBeNull()
  })

  it('navigates from the catalog, waits for the target map data and opens the fresh anchor', async () => {
    const user = userEvent.setup()
    const fresh = { ...catalogAnchor, name: 'Catalog fresh', x: 45, y: 55 }
    updateAnchor.mockResolvedValueOnce({ data: fresh })
    listLocationAnchors.mockImplementation((locationId) => Promise.resolve(
      locationId === 20 ? [fresh] : [],
    ))
    render(<GPSDashboard />)
    await screen.findByText(/FLOOR_1\|blob:/)

    await user.click(screen.getByRole('button', { name: 'Quản lý Anchor' }))

    expect(await screen.findByText(/WAREHOUSE\|blob:/)).toBeTruthy()
    expect((await screen.findByLabelText('Tên Anchor')).value).toBe('Catalog fresh')
    expect(screen.getByLabelText('MAC Address').disabled).toBe(true)
    expect(listLocationAnchors).toHaveBeenCalledWith(20, expect.any(Object))
    await user.click(screen.getByRole('button', { name: 'Lưu Anchor' }))
    expect(updateAnchor).toHaveBeenCalledWith(88, {
      name: 'Catalog fresh', x: 45, y: 55, z: 0,
    })
  })

  it('cancels list navigation with an error when the target map is no longer accessible', async () => {
    const user = userEvent.setup()
    listGroupMaps.mockImplementation((groupId) => Promise.resolve(
      groupId === 2 ? [] : mapsByGroup[groupId] || [],
    ))
    render(<GPSDashboard />)
    await screen.findByText(/FLOOR_1\|blob:/)

    await user.click(screen.getByRole('button', { name: 'Quản lý Anchor' }))

    expect((await screen.findByRole('alert')).textContent).toContain('không còn quyền truy cập')
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('shows catalog access for a flagged user but not an unflagged user', async () => {
    authState.user = { user_id: 7, role: 'user', can_config_anchor: 'no' }
    const { rerender } = render(<GPSDashboard />)
    await screen.findByText(/FLOOR_1\|blob:/)
    expect(screen.queryByRole('button', { name: 'Quản lý Anchor' })).toBeNull()

    authState.user = { user_id: 7, role: 'user', can_config_anchor: 'yes' }
    rerender(<GPSDashboard />)
    expect(screen.getByRole('button', { name: 'Quản lý Anchor' })).toBeTruthy()
  })
})
