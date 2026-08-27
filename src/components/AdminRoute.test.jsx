import React from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import AdminRoute from './AdminRoute'

const auth = vi.hoisted(() => ({ user: { role: 'admin' }, loading: false }))
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => auth }))

afterEach(() => {
  cleanup()
  auth.user = { role: 'admin' }
  auth.loading = false
})

describe('AdminRoute', () => {
  it('renders the Ping route for admins', () => {
    render(
      <MemoryRouter initialEntries={['/ping']}>
        <Routes>
          <Route element={<AdminRoute />}>
            <Route path="/ping" element={<div>Ping admin page</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByText('Ping admin page')).toBeTruthy()
  })

  it('does not render the Ping route for non-admin users', () => {
    auth.user = { role: 'user' }
    render(
      <MemoryRouter initialEntries={['/ping']}>
        <Routes>
          <Route element={<AdminRoute />}>
            <Route path="/ping" element={<div>Ping admin page</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.queryByText('Ping admin page')).toBeNull()
    expect(screen.getByText('403 Forbidden')).toBeTruthy()
  })
})
