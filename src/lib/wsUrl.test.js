import { beforeEach, describe, expect, it, vi } from 'vitest'

import { wsUrl } from './wsUrl'

describe('WebSocket authentication transport', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('never places the access token in the WebSocket URL', () => {
    localStorage.setItem('iot_token', 'header.payload.signature')

    const url = wsUrl('/ws/global', 'ws://localhost')

    expect(url).toBe('ws://localhost/ws/global')
    expect(url).not.toContain('header.payload.signature')
    expect(url).not.toContain('access_token')
  })

  it('opens the socket with the JWT in the negotiated subprotocol header', async () => {
    localStorage.setItem('iot_token', 'header.payload.signature')
    const WebSocketMock = vi.fn()
    const { openWebSocket } = await import('./wsUrl')

    openWebSocket('/ws/global', 'ws://localhost', WebSocketMock)

    expect(WebSocketMock).toHaveBeenCalledWith(
      'ws://localhost/ws/global',
      ['iot-jwt', 'header.payload.signature'],
    )
  })
})
