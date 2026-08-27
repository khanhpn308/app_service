import React from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import Layout from './Layout'

const auth = vi.hoisted(() => ({ admin: false }))
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    logout: vi.fn(),
    user: { username: 'admin', role: 'admin' },
    isAdmin: () => auth.admin,
  }),
}))

afterEach(() => {
  cleanup()
  auth.admin = false
})

describe('Layout dashboard navigation', () => {
  it('shows dashboard destinations in a horizontal navigation row', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard/gps']}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="dashboard/gps" element={<div>GPS content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    const menu = screen.getByRole('navigation', { name: 'Điều hướng Dashboard' })

    expect(menu.className).toContain('flex-row')
    expect(screen.getByRole('link', { name: 'Telemetry' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Asset & worker Tracking' })).toBeTruthy()
  })

  it('uses a full-bleed main region only for the GPS dashboard', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard/gps']}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="dashboard/gps" element={<div>GPS content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    const main = screen.getByRole('main')
    expect(main.className).toContain('max-w-none')
    expect(main.className).toContain('p-0')
  })

  it('shows the Ping navigation only for admins', () => {
    auth.admin = true
    render(
      <MemoryRouter initialEntries={['/home']}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="home" element={<div>Home content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getAllByRole('link', { name: 'Ping' }).length).toBeGreaterThan(0)

    cleanup()
    auth.admin = false
    render(
      <MemoryRouter initialEntries={['/home']}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="home" element={<div>Home content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.queryByRole('link', { name: 'Ping' })).toBeNull()
  })
})
