import React from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import GPSPage from './GPSPage'
import { apiFetch } from '../lib/api'
import { openWebSocket } from '../lib/wsUrl'

let adminRole = false

function isAdminMock() {
  return adminRole
}

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ isAdmin: isAdminMock }),
}))

vi.mock('../lib/api', () => ({
  apiFetch: vi.fn(),
}))

vi.mock('../lib/wsUrl', () => ({
  openWebSocket: vi.fn(),
}))

vi.mock('../components/Dashboard/GPS/GPSDashboard', () => ({
  default: ({ initialDevices }) => (
    <div data-testid="gps-dashboard">{initialDevices.length}</div>
  ),
}))

describe('GPSPage device catalog authorization', () => {
  afterEach(cleanup)

  beforeEach(() => {
    adminRole = false
    apiFetch.mockResolvedValue([])
    openWebSocket.mockReturnValue({
      close: vi.fn(),
      onmessage: null,
      onclose: null,
    })
  })

  it('loads only authorized devices for a regular user', async () => {
    render(<GPSPage />)

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith('/api/devices/my')
    })
  })

  it('loads the complete device catalog for an admin', async () => {
    adminRole = true
    render(<GPSPage />)

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith('/api/devices')
    })
  })

  it('renders the dashboard in a full-bleed viewport shell', async () => {
    render(<GPSPage />)

    await screen.findByTestId('gps-dashboard')
    const shell = screen.getByTestId('gps-page-shell')
    expect(shell.className).toContain('w-full')
    expect(shell.className).not.toContain('rounded-xl')
    expect(shell.className).not.toContain('shadow-xl')
  })
})
