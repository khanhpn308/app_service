/**
 * Chuẩn hoá trạng thái thiết bị về dạng UI thống nhất.
 *
 * Nguồn dữ liệu không đồng nhất:
 * - Backend trả `status`: "active" / "deactive".
 * - Mock data (mockData.js) dùng "online" / "offline".
 *
 * UI chỉ quan tâm 2 trạng thái: 'online' | 'offline'.
 */

/** Map status thô (active/deactive hoặc online/offline) → 'online' | 'offline'. */
export function toUiStatus(raw) {
  const s = String(raw ?? '').trim().toLowerCase();
  if (s === 'active' || s === 'online') return 'online';
  return 'offline';
}

/** Tiện ích boolean: thiết bị có đang online không. */
export function isOnline(raw) {
  return toUiStatus(raw) === 'online';
}
