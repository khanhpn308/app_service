/**
 * Client HTTP gọi FastAPI — fetch wrapper thống nhất.
 *
 * - `VITE_API_URL`: base URL backend (Vite env). Rỗng = cùng origin (dev proxy hoặc CDN chung).
 * - `skipAuth: true`: không gắn Bearer (login, public bootstrap, …).
 * - Lỗi: đọc `detail` từ JSON (FastAPI) hoặc `statusText`; ném `Error` để UI bắt.
 *
 * @param {string} path - Đường dẫn từ gốc API, ví dụ `/api/auth/me`
 * @param {RequestInit & { skipAuth?: boolean }} [options] - Tuỳ chọn fetch; `skipAuth` loại trừ header JWT
 * @returns {Promise<any>} JSON đã parse hoặc null nếu body rỗng
 */
const API_BASE = import.meta.env.VITE_API_URL ?? '';

function prepareRequest(options) {
  const skipAuth = options.skipAuth === true;
  const token = skipAuth ? null : localStorage.getItem('iot_token');
  const isFormData = options.body instanceof FormData
  const headers = { ...options.headers };
  if (!isFormData && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const { skipAuth: _skip, ...fetchOptions } = options;
  return { ...fetchOptions, headers }
}

async function throwResponseError(res) {
  const text = await res.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = text
  }
  let message = res.statusText
  if (data && typeof data === 'object' && data.detail != null) {
    const detail = data.detail
    if (typeof detail === 'string') {
      message = detail
    } else if (Array.isArray(detail)) {
      message = detail.map((item) => item.msg || JSON.stringify(item)).join(', ')
    } else {
      message = JSON.stringify(detail)
    }
  }
  const error = new Error(message || 'Request failed')
  error.status = res.status
  throw error
}

export async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...prepareRequest(options),
  });
  if (!res.ok) {
    await throwResponseError(res)
  }
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  return data;
}

export async function apiFetchBlob(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...prepareRequest(options),
  })
  if (!res.ok) {
    await throwResponseError(res)
  }
  return res.blob()
}
