// @vitest-environment jsdom

import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import AnchorEditorDialog from './AnchorEditorDialog'
import MapViewer from './MapViewer'

const anchor = {
  anchor_id: 31,
  mac_address: '12:21:AA:43:1A:9F',
  hardware_id: 'AA:01',
  name: 'Alpha',
  x: 25,
  y: 40,
  z: 1,
}

const viewerProps = {
  locationName: 'FLOOR_1',
  floorplanUrl: 'blob:map',
  isLoading: false,
  hasError: false,
  devices: [],
  anchors: [anchor],
  getColor: () => '#123456',
  getDeviceName: () => '',
}

describe('Phase 2 Anchor map UI', () => {
  afterEach(cleanup)

  it('renders a distinct non-interactive viewer marker at percentage coordinates', () => {
    render(
      <MapViewer
        {...viewerProps}
        anchors={[{ ...anchor, x: 6.21850631, y: 89.23413299 }]}
        canConfigureAnchors={false}
      />,
    )
    const marker = screen.getByLabelText('Anchor Alpha')
    expect(marker.tagName).toBe('DIV')
    expect(marker.style.left).toBe('6.22%')
    expect(marker.style.top).toBe('10.77%')
    expect(marker.className).not.toContain('cursor-pointer')
    expect(screen.queryByRole('button', { name: 'Anchor Alpha' })).toBeNull()
  })

  it('lets a config user select and drag a draft using the map bounding box', () => {
    const onAnchorClick = vi.fn()
    const onAnchorMove = vi.fn()
    render(
      <MapViewer
        {...viewerProps}
        canConfigureAnchors
        onAnchorClick={onAnchorClick}
        onAnchorMove={onAnchorMove}
      />,
    )
    const overlay = screen.getByTestId('map-coordinate-overlay')
    overlay.getBoundingClientRect = () => ({
      left: 100,
      top: 50,
      width: 400,
      height: 200,
      right: 500,
      bottom: 250,
      x: 100,
      y: 50,
      toJSON: () => ({}),
    })
    const marker = screen.getByRole('button', { name: 'Anchor Alpha' })
    fireEvent.pointerDown(marker, { clientX: 200, clientY: 150, pointerId: 1 })
    fireEvent.pointerMove(overlay, { clientX: 233.333, clientY: 156.789, pointerId: 1 })
    fireEvent.pointerUp(overlay, { pointerId: 1 })

    expect(onAnchorClick).toHaveBeenCalledWith(anchor)
    expect(onAnchorClick).toHaveBeenCalledTimes(1)
    expect(onAnchorMove).toHaveBeenLastCalledWith(anchor, 33.33, 46.61)
  })

  it('opens the editor from a direct marker click without a second reset callback', async () => {
    const user = userEvent.setup()
    const onAnchorClick = vi.fn()
    render(<MapViewer {...viewerProps} canConfigureAnchors onAnchorClick={onAnchorClick} />)

    await user.click(screen.getByRole('button', { name: 'Anchor Alpha' }))
    expect(onAnchorClick).toHaveBeenCalledOnce()
    expect(onAnchorClick).toHaveBeenCalledWith(anchor)
  })

  it('keeps create coordinates as draft and submits numeric values once', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(
      <AnchorEditorDialog
        mode="create"
        anchor={{ mac_address: '', name: '', x: 50, y: 50, z: 0 }}
        onChange={vi.fn()}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    )
    await user.type(screen.getByLabelText('MAC Address'), '12:21:AA:43:1A:9F')
    await user.type(screen.getByLabelText('Tên Anchor'), 'Alpha')
    await user.clear(screen.getByLabelText('Tọa độ X'))
    await user.type(screen.getByLabelText('Tọa độ X'), '42.567')
    await user.click(screen.getByRole('button', { name: 'Lưu Anchor' }))

    expect(onSave).toHaveBeenCalledTimes(1)
    expect(onSave).toHaveBeenCalledWith({
      mac_address: '12:21:AA:43:1A:9F',
      name: 'Alpha',
      x: 42.56,
      y: 50,
      z: 0,
    })
  })

  it('uses a normalized MAC address as the Anchor hardware identity', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(
      <AnchorEditorDialog
        mode="create"
        anchor={{ mac_address: '', name: '', x: 50, y: 50, z: 0 }}
        onChange={vi.fn()}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    )

    const macInput = screen.getByLabelText('MAC Address')
    expect(macInput.placeholder).toBe('12:21:AA:43:1A:9F')
    await user.type(macInput, '12:21:aa:43:1f:9b')
    await user.type(screen.getByLabelText('Tên Anchor'), 'MAC Anchor')
    await user.click(screen.getByRole('button', { name: 'Lưu Anchor' }))

    expect(onSave).toHaveBeenCalledWith({
      mac_address: '12:21:AA:43:1F:9B',
      name: 'MAC Anchor',
      x: 50,
      y: 50,
      z: 0,
    })
  })

  it('shows a validation error for a malformed MAC address', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(
      <AnchorEditorDialog
        mode="create"
        anchor={{ mac_address: '', name: '', x: 50, y: 50, z: 0 }}
        onChange={vi.fn()}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    )

    await user.type(screen.getByLabelText('MAC Address'), '12:21:aa:43:jh')
    await user.type(screen.getByLabelText('Tên Anchor'), 'Invalid MAC')
    await user.click(screen.getByRole('button', { name: 'Lưu Anchor' }))

    expect(screen.getByRole('alert').textContent).toContain('MAC Address')
    expect(onSave).not.toHaveBeenCalled()
  })

  it('allows a legacy Anchor to receive its MAC Address once', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(
      <AnchorEditorDialog
        mode="edit"
        anchor={{ ...anchor, mac_address: null, hardware_id: '978294' }}
        onChange={vi.fn()}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    )

    const macInput = screen.getByLabelText('MAC Address')
    expect(macInput.disabled).toBe(false)
    expect(macInput.value).toBe('')
    await user.type(macInput, '12:21:aa:43:1a:29')
    await user.click(screen.getByRole('button', { name: 'Lưu Anchor' }))

    expect(onSave).toHaveBeenCalledWith({
      mac_address: '12:21:AA:43:1A:29',
      name: 'Alpha',
      x: 25,
      y: 40,
      z: 1,
    })
  })

  it('normalizes displayed coordinates to two decimals and uses a compact coordinate row', () => {
    render(
      <AnchorEditorDialog
        mode="edit"
        anchor={{ ...anchor, x: 6.21850631, y: 89.23413299, z: 0.005 }}
        onChange={vi.fn()}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    const xInput = screen.getByLabelText('Tọa độ X')
    expect(xInput.value).toBe('6.22')
    expect(screen.getByLabelText('Tọa độ Y').value).toBe('89.23')
    expect(screen.getByLabelText('Tọa độ Z').value).toBe('0.01')
    expect(xInput.step).toBe('0.01')
    expect(xInput.closest('label').parentElement.className).toContain('sm:w-1/2')
    expect(xInput.className).toContain('[appearance:textfield]')

    fireEvent.change(xInput, { target: { value: '8.329' } })
    expect(xInput.value).toBe('6.22')
    fireEvent.change(xInput, { target: { value: '8.32' } })
    expect(xInput.value).toBe('8.32')
  })

  it('locks MAC Address after assignment and confirms soft delete', async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(
      <AnchorEditorDialog
        mode="edit"
        anchor={anchor}
        onChange={vi.fn()}
        onSave={vi.fn()}
        onDelete={onDelete}
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByLabelText('MAC Address').disabled).toBe(true)
    await user.click(screen.getByRole('button', { name: 'Xóa Anchor' }))
    expect(window.confirm).toHaveBeenCalled()
    expect(onDelete).toHaveBeenCalledTimes(1)
  })

  it('renders the cancel action with an explicit visible secondary style', () => {
    render(
      <AnchorEditorDialog
        mode="create"
        anchor={{ mac_address: '', name: '', x: 50, y: 50, z: 0 }}
        onChange={vi.fn()}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    const cancelButton = screen.getByRole('button', { name: 'Hủy' })
    expect(cancelButton.className).toContain('bg-slate-100')
    expect(cancelButton.className).toContain('text-slate-700')
    expect(cancelButton.className).toContain('hover:bg-slate-200')
    expect(cancelButton.className).toContain('focus-visible:ring-2')
  })
})
