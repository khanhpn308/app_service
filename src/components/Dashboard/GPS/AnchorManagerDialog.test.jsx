import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AnchorManagerDialog from './AnchorManagerDialog'
import { manageAnchors } from '../../../lib/anchorsApi'
import { listGroupMaps } from '../../../lib/mapsApi'

vi.mock('../../../lib/anchorsApi', () => ({ manageAnchors: vi.fn() }))
vi.mock('../../../lib/mapsApi', () => ({ listGroupMaps: vi.fn() }))

const groups = [
  { group_id: 1, name: 'Factory', access_role: 'owner' },
  { group_id: 2, name: 'Warehouse', access_role: 'admin' },
]
const anchor = {
  anchor_id: 31,
  mac_address: '12:21:AA:43:1A:31',
  hardware_id: 'AA:01',
  name: 'Door',
  group_id: 1,
  location_id: 10,
  location: 'FLOOR_1',
  x: 10.5,
  y: 20,
  z: 1.25,
  updated_at: '2026-08-07T10:00:00Z',
}

describe('AnchorManagerDialog', () => {
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  beforeEach(() => {
    manageAnchors.mockResolvedValue({ data: [anchor], total: 26, limit: 25, offset: 0 })
    listGroupMaps.mockResolvedValue([{ location_id: 10, location: 'FLOOR_1', group_id: 1 }])
  })

  it('searches after 300ms and filters by group and map with a page size of 25', async () => {
    const user = userEvent.setup()
    render(<AnchorManagerDialog groups={groups} onSelect={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'Quản lý Anchor' }))
    await screen.findByText('12:21:AA:43:1A:31')
    expect(manageAnchors).toHaveBeenCalledWith(
      { q: '', groupId: undefined, locationId: undefined, limit: 25, offset: 0 },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )

    fireEvent.change(screen.getByLabelText('Tìm Anchor'), { target: { value: 'door' } })
    expect(manageAnchors).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(manageAnchors).toHaveBeenLastCalledWith(
      { q: 'door', groupId: undefined, locationId: undefined, limit: 25, offset: 0 },
      expect.any(Object),
    ))

    fireEvent.change(screen.getByLabelText('Lọc theo nhóm'), { target: { value: '1' } })
    await waitFor(() => expect(listGroupMaps).toHaveBeenCalledWith(1))
    fireEvent.change(screen.getByLabelText('Lọc theo map'), { target: { value: '10' } })
    await waitFor(() => expect(manageAnchors).toHaveBeenLastCalledWith(
      { q: 'door', groupId: 1, locationId: 10, limit: 25, offset: 0 },
      expect.any(Object),
    ))
  })

  it('shows required fields, paginates and closes before selecting a row', async () => {
    const onSelect = vi.fn()
    const user = userEvent.setup()
    render(<AnchorManagerDialog groups={groups} onSelect={onSelect} />)
    await user.click(screen.getByRole('button', { name: 'Quản lý Anchor' }))

    expect(await screen.findByText('Door')).toBeTruthy()
    for (const text of ['#31', '12:21:AA:43:1A:31', '10.5', '20', '1.25']) {
      expect(screen.getByText(text)).toBeTruthy()
    }
    expect(screen.getByText(/Factory \/ FLOOR_1/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Trang sau' }))
    await waitFor(() => expect(manageAnchors).toHaveBeenLastCalledWith(
      { q: '', groupId: undefined, locationId: undefined, limit: 25, offset: 25 },
      expect.any(Object),
    ))

    await user.click(screen.getByRole('button', { name: 'Cấu hình Anchor Door' }))
    expect(onSelect).toHaveBeenCalledWith(anchor)
    expect(screen.queryByRole('dialog', { name: 'Quản lý Anchor' })).toBeNull()
  })
})
