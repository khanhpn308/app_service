import React from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Ping from './Ping'
import { apiFetch } from '../lib/api'
import { openWebSocket } from '../lib/wsUrl'

vi.mock('../lib/api', () => ({ apiFetch: vi.fn() }))
vi.mock('../lib/wsUrl', () => ({ openWebSocket: vi.fn() }))

const devices = [
  { device_id: 101, devicename: 'Node 101' },
  { device_id: 202, devicename: 'Node 202' },
]

function createSocket() {
  return {
    close: vi.fn(),
    onmessage: null,
    onclose: null,
    onerror: null,
  }
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function summary(deviceId, overrides = {}) {
  return {
    device_id: String(deviceId),
    total_payload: 3,
    current_payload: { id: 3, order: 7, timestamp: 12345 },
    total_missing_payload: 2,
    ...overrides,
  }
}

describe('Ping admin summary page', () => {
  beforeEach(() => {
    openWebSocket.mockImplementation(() => createSocket())
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  it('loads the device catalog, selects the first device and renders exactly three summary cards', async () => {
    apiFetch.mockImplementation(async (path) => {
      if (path === '/api/devices?limit=1000') return devices
      if (path === '/api/pings/101/summary') return summary(101)
      throw new Error(`Unexpected path: ${path}`)
    })

    render(<Ping />)

    expect(screen.getByText('Đang tải danh sách thiết bị...')).toBeTruthy()
    expect(await screen.findByRole('option', { name: 'Node 101 (101)' })).toBeTruthy()
    expect(screen.getByLabelText('Lọc theo Device ID').value).toBe('101')

    const cards = await screen.findAllByTestId('ping-stat-card')
    expect(cards).toHaveLength(3)
    expect(within(cards[0]).getByText('Total payload')).toBeTruthy()
    expect(within(cards[0]).getByText('3')).toBeTruthy()
    expect(within(cards[1]).getByText('Current payload')).toBeTruthy()
    expect(within(cards[1]).getByText('Order 7')).toBeTruthy()
    expect(within(cards[1]).getByText('Node uptime (ms): 12345')).toBeTruthy()
    expect(within(cards[2]).getByText('Total missing payload')).toBeTruthy()
    expect(within(cards[2]).getByText('2')).toBeTruthy()
    expect(apiFetch).toHaveBeenCalledWith('/api/devices?limit=1000')
    expect(apiFetch).toHaveBeenCalledWith('/api/pings/101/summary')
  })

  it('switches device and renders the documented zero state', async () => {
    apiFetch.mockImplementation(async (path) => {
      if (path === '/api/devices?limit=1000') return devices
      if (path === '/api/pings/101/summary') return summary(101)
      if (path === '/api/pings/202/summary') {
        return summary(202, {
          total_payload: 0,
          current_payload: null,
          total_missing_payload: 0,
        })
      }
      throw new Error(`Unexpected path: ${path}`)
    })

    render(<Ping />)
    const select = await screen.findByLabelText('Lọc theo Device ID')
    await screen.findByText('Order 7')
    fireEvent.change(select, { target: { value: '202' } })

    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith('/api/pings/202/summary'))
    expect(await screen.findByText('Chưa có payload ping')).toBeTruthy()
    const cards = screen.getAllByTestId('ping-stat-card')
    expect(within(cards[0]).getByText('0')).toBeTruthy()
    expect(within(cards[1]).getByText('—')).toBeTruthy()
    expect(within(cards[2]).getByText('0')).toBeTruthy()
  })

  it('shows catalog and summary errors without exposing raw payload data', async () => {
    apiFetch.mockRejectedValueOnce(new Error('Không tải được catalog'))
    render(<Ping />)

    expect((await screen.findByRole('alert')).textContent).toContain('Không tải được catalog')
    expect(screen.queryByText(/payload-secret/)).toBeNull()

    cleanup()
    apiFetch.mockReset()
    apiFetch.mockImplementation(async (path) => {
      if (path === '/api/devices?limit=1000') return devices
      throw new Error('Không tải được thống kê')
    })
    render(<Ping />)
    expect((await screen.findByRole('alert')).textContent).toContain('Không tải được thống kê')
  })

  it('refreshes only matching events and coalesces an event burst to one queued request', async () => {
    const socket = createSocket()
    openWebSocket.mockReturnValue(socket)
    const firstRefresh = deferred()
    const queuedRefresh = deferred()
    let summaryCalls = 0
    apiFetch.mockImplementation((path) => {
      if (path === '/api/devices?limit=1000') return Promise.resolve(devices)
      if (path === '/api/pings/101/summary') {
        summaryCalls += 1
        if (summaryCalls === 1) return Promise.resolve(summary(101))
        if (summaryCalls === 2) return firstRefresh.promise
        if (summaryCalls === 3) return queuedRefresh.promise
      }
      throw new Error(`Unexpected path: ${path}`)
    })

    render(<Ping />)
    await screen.findByText('Order 7')
    expect(openWebSocket).toHaveBeenCalledWith('/ws/pings')

    act(() => {
      socket.onmessage({ data: JSON.stringify({ type: 'ping_stats_updated', device_id: '202', reason: 'received' }) })
    })
    expect(summaryCalls).toBe(1)

    act(() => {
      socket.onmessage({ data: JSON.stringify({ type: 'ping_stats_updated', device_id: '101', reason: 'received' }) })
      socket.onmessage({ data: JSON.stringify({ type: 'ping_stats_updated', device_id: '101', reason: 'received' }) })
      socket.onmessage({ data: JSON.stringify({ type: 'ping_stats_updated', device_id: '101', reason: 'received' }) })
    })
    expect(summaryCalls).toBe(2)

    await act(async () => firstRefresh.resolve(summary(101, { total_payload: 4 })))
    await waitFor(() => expect(summaryCalls).toBe(3))
    await act(async () => queuedRefresh.resolve(summary(101, { total_payload: 5 })))
    expect(await screen.findByText('5')).toBeTruthy()
  })

  it('does not let an old selection response overwrite the current device', async () => {
    const socket = createSocket()
    openWebSocket.mockReturnValue(socket)
    const oldRefresh = deferred()
    const selectedRefresh = deferred()
    let device101Calls = 0
    apiFetch.mockImplementation((path) => {
      if (path === '/api/devices?limit=1000') return Promise.resolve(devices)
      if (path === '/api/pings/101/summary') {
        device101Calls += 1
        return device101Calls === 1 ? Promise.resolve(summary(101)) : oldRefresh.promise
      }
      if (path === '/api/pings/202/summary') return selectedRefresh.promise
      throw new Error(`Unexpected path: ${path}`)
    })

    render(<Ping />)
    const select = await screen.findByLabelText('Lọc theo Device ID')
    await screen.findByText('Order 7')
    act(() => {
      socket.onmessage({ data: JSON.stringify({ type: 'ping_stats_updated', device_id: '101', reason: 'received' }) })
    })
    fireEvent.change(select, { target: { value: '202' } })
    await act(async () => selectedRefresh.resolve(summary(202, {
      total_payload: 20,
      current_payload: { id: 20, order: 22, timestamp: 20200 },
    })))
    expect(await screen.findByText('Order 22')).toBeTruthy()

    await act(async () => oldRefresh.resolve(summary(101, {
      total_payload: 99,
      current_payload: { id: 99, order: 99, timestamp: 99999 },
    })))
    expect(screen.getByText('Order 22')).toBeTruthy()
    expect(screen.queryByText('Order 99')).toBeNull()
  })

  it('reconnects after about 1200 ms and cleans up the socket and timer on unmount', async () => {
    vi.useFakeTimers()
    const sockets = []
    openWebSocket.mockImplementation(() => {
      const socket = createSocket()
      sockets.push(socket)
      return socket
    })
    apiFetch.mockImplementation(async (path) => {
      if (path === '/api/devices?limit=1000') return devices
      if (path === '/api/pings/101/summary') return summary(101)
      throw new Error(`Unexpected path: ${path}`)
    })

    const view = render(<Ping />)
    await act(async () => Promise.resolve())
    expect(sockets).toHaveLength(1)
    act(() => sockets[0].onclose())
    act(() => vi.advanceTimersByTime(1199))
    expect(sockets).toHaveLength(1)
    act(() => vi.advanceTimersByTime(1))
    expect(sockets).toHaveLength(2)

    act(() => sockets[1].onclose())
    view.unmount()
    act(() => vi.advanceTimersByTime(1200))
    expect(sockets).toHaveLength(2)
    expect(sockets[1].close).toHaveBeenCalledOnce()
  })

  it('shows the selected device in the destructive dialog and cancel does not call DELETE', async () => {
    const user = userEvent.setup()
    apiFetch.mockImplementation(async (path) => {
      if (path === '/api/devices?limit=1000') return devices
      if (path === '/api/pings/101/summary') return summary(101)
      throw new Error(`Unexpected path: ${path}`)
    })

    render(<Ping />)
    await screen.findByText('Order 7')
    await user.click(screen.getByRole('button', { name: 'Xóa dữ liệu ping' }))

    const dialog = screen.getByRole('alertdialog')
    expect(within(dialog).getByText(/Device ID: 101/)).toBeTruthy()
    expect(within(dialog).getByText(/ping_payload/)).toBeTruthy()
    expect(within(dialog).getByText(/missing_ping_payload/)).toBeTruthy()
    await user.click(within(dialog).getByRole('button', { name: 'Hủy' }))
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(apiFetch.mock.calls.some(([, options]) => options?.method === 'DELETE')).toBe(false)
  })

  it('prevents double submit, closes after delete and refetches the zero state', async () => {
    const user = userEvent.setup()
    const deleteRequest = deferred()
    let summaryCalls = 0
    apiFetch.mockImplementation((path, options) => {
      if (path === '/api/devices?limit=1000') return Promise.resolve(devices)
      if (path === '/api/pings/101/summary') {
        summaryCalls += 1
        return Promise.resolve(summary(101, summaryCalls === 1 ? {} : {
          total_payload: 0,
          current_payload: null,
          total_missing_payload: 0,
        }))
      }
      if (path === '/api/pings/101' && options?.method === 'DELETE') return deleteRequest.promise
      throw new Error(`Unexpected path: ${path}`)
    })

    render(<Ping />)
    await screen.findByText('Order 7')
    await user.click(screen.getByRole('button', { name: 'Xóa dữ liệu ping' }))
    const confirm = screen.getByRole('button', { name: 'Xác nhận xóa' })
    await user.click(confirm)
    expect(screen.getByRole('button', { name: 'Đang xóa...' }).disabled).toBe(true)
    expect(apiFetch.mock.calls.filter(([, options]) => options?.method === 'DELETE')).toHaveLength(1)

    await act(async () => deleteRequest.resolve({ ok: true, predicted_order: 1 }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(await screen.findByText('Chưa có payload ping')).toBeTruthy()
    const cards = screen.getAllByTestId('ping-stat-card')
    expect(within(cards[0]).getByText('0')).toBeTruthy()
    expect(within(cards[2]).getByText('0')).toBeTruthy()
  })

  it('keeps the confirmation dialog open and reports a server delete error', async () => {
    const user = userEvent.setup()
    apiFetch.mockImplementation(async (path, options) => {
      if (path === '/api/devices?limit=1000') return devices
      if (path === '/api/pings/101/summary') return summary(101)
      if (path === '/api/pings/101' && options?.method === 'DELETE') {
        throw new Error('Không thể xóa dữ liệu ping')
      }
      throw new Error(`Unexpected path: ${path}`)
    })

    render(<Ping />)
    await screen.findByText('Order 7')
    await user.click(screen.getByRole('button', { name: 'Xóa dữ liệu ping' }))
    await user.click(screen.getByRole('button', { name: 'Xác nhận xóa' }))

    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(screen.getByRole('alert').textContent).toContain('Không thể xóa dữ liệu ping')
    expect(screen.getByRole('alertdialog')).toBeTruthy()
  })
})
