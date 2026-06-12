/**
 * Dựng URL WebSocket có kèm JWT để backend xác thực.
 *
 * Backend yêu cầu mọi WS client (frontend) gửi token qua query `?access_token=`
 * (trình duyệt không set được custom header trong WS handshake). Token đọc từ
 * `localStorage('iot_token')` — cùng key với `lib/api.js`.
 *
 * @param {string} path - Đường dẫn WS từ gốc, ví dụ `/ws/global` hoặc `/ws/devices/123`
 * @param {string} [base] - Base tuỳ chọn (vd `VITE_WS_URL`). Rỗng = auto từ origin hiện tại.
 * @returns {string} URL đầy đủ kèm token (nếu có)
 */
export function wsUrl(path, base) {
  let origin = base;
  if (!origin) {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    origin = `${proto}://${window.location.host}`;
  }
  const token = localStorage.getItem('iot_token');
  const sep = path.includes('?') ? '&' : '?';
  return token
    ? `${origin}${path}${sep}access_token=${encodeURIComponent(token)}`
    : `${origin}${path}`;
}
