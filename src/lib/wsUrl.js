/**
 * Dựng URL WebSocket không chứa credential.
 *
 * @param {string} path - Đường dẫn WS từ gốc, ví dụ `/ws/global` hoặc `/ws/devices/123`
 * @param {string} [base] - Base tuỳ chọn (vd `VITE_WS_URL`). Rỗng = auto từ origin hiện tại.
 * @returns {string} URL đầy đủ
 */
export function wsUrl(path, base) {
  let origin = base;
  if (!origin) {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    origin = `${proto}://${window.location.host}`;
  }
  return `${origin}${path}`;
}

/**
 * Mở WebSocket với JWT trong Sec-WebSocket-Protocol thay vì query string.
 * Token không xuất hiện trong access log của reverse proxy hoặc Uvicorn.
 */
export function openWebSocket(path, base, WebSocketImpl = WebSocket) {
  const token = localStorage.getItem('iot_token');
  const url = wsUrl(path, base);
  return token
    ? new WebSocketImpl(url, ['iot-jwt', token])
    : new WebSocketImpl(url);
}
