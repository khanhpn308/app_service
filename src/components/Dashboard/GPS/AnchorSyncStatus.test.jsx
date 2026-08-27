import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import AnchorSyncStatus from './AnchorSyncStatus'
import * as anchorsApi from '@/lib/anchorsApi'

vi.mock('@/lib/anchorsApi', async () => {
  const actual = await vi.importActual('@/lib/anchorsApi')
  return { ...actual, getAnchorConfigStatus: vi.fn(), resyncAnchorConfig: vi.fn() }
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('AnchorSyncStatus', () => {
  it('polls status, shows per-gateway detail and resyncs', async () => {
    anchorsApi.getAnchorConfigStatus.mockResolvedValue({
      aggregate: 'partial', revision: 7, anchor_count: 2,
      gateways: [{
        gateway_id: 101, devicename: 'Gateway A', online: false,
        last_seen_at: '2026-08-08T10:00:00Z', target_revision: 7,
        applied_revision: 6, delivery_status: 'published', error: null,
      }],
    })
    anchorsApi.resyncAnchorConfig.mockResolvedValue({ gateway_id: 101, config_revision: 8, sync_status: 'pending' })

    render(<AnchorSyncStatus locationId={12} enabled />)
    expect(await screen.findByRole('button', { name: /đồng bộ anchor: một phần/i })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /đồng bộ anchor/i }))
    expect(screen.getByText(/Gateway A.*101/)).toBeTruthy()
    expect(screen.getByText(/offline/i)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /^gửi lại cấu hình$/i })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /gửi lại cấu hình cho gateway a.*101/i }))
    await waitFor(() => expect(anchorsApi.resyncAnchorConfig).toHaveBeenCalledWith(12, 101))
    expect(await screen.findByText(/revision 8.*gateway 101/i)).toBeTruthy()
  })

  it('does not request status when viewer has no config permission', () => {
    render(<AnchorSyncStatus locationId={12} enabled={false} />)
    expect(anchorsApi.getAnchorConfigStatus).not.toHaveBeenCalled()
  })

  it('opens the no-gateway details in an accessible modal outside clipped containers', async () => {
    anchorsApi.getAnchorConfigStatus.mockResolvedValue({
      aggregate: 'no_gateway', revision: 18, anchor_count: 0, gateways: [],
    })

    render(
      <div data-testid="clipped-parent" className="overflow-hidden">
        <AnchorSyncStatus locationId={12} enabled />
      </div>,
    )

    fireEvent.click(await screen.findByRole('button', { name: /không có gateway/i }))
    const dialog = screen.getByRole('dialog', { name: 'Đồng bộ Anchor' })

    expect(dialog.closest('[data-testid="clipped-parent"]')).toBeNull()
    expect(screen.getByText('Không có Gateway active khớp location.')).toBeTruthy()
  })
})
