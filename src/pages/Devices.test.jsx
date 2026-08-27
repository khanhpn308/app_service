import React from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import Devices from './Devices'
import { apiFetch } from '../lib/api'

vi.mock('../lib/api', () => ({ apiFetch: vi.fn() }))
vi.mock('../lib/wsUrl', () => ({
  openWebSocket: vi.fn(() => ({ close: vi.fn(), onmessage: null })),
}))
const auth = vi.hoisted(() => ({ isAdmin: vi.fn(() => true) }))
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => auth,
}))

describe('Devices device type labels', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders a gateway device as Gateway instead of Temperature', async () => {
    apiFetch.mockImplementation(async (path) => {
      if (path === '/api/devices') {
        return [{
          device_id: 613680,
          devicename: 'Floor uplink',
          device_type: 'gateway',
          location: 'ad00000',
          status: 'active',
        }]
      }
      if (path === '/api/users') return []
      return []
    })

    render(
      <MemoryRouter>
        <Devices />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Gateway')).toBeTruthy()
    expect(screen.queryByText('Temperature')).toBeNull()
  })
})
