const API_BASE = import.meta.env.VITE_API_URL ?? '';

/**
 * @param {string} path
 * @param {RequestInit} [options]
 */
export async function apiFetch(path, options = {}) {
  const skipAuth = options.skipAuth === true;
  const token = skipAuth ? null : localStorage.getItem('iot_token');
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const { skipAuth: _skip, ...fetchOptions } = options;
  const res = await fetch(`${API_BASE}${path}`, {
    ...fetchOptions,
    headers,
  });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    let msg = res.statusText;
    if (data && typeof data === 'object' && data.detail != null) {
      const d = data.detail;
      if (typeof d === 'string') {
        msg = d;
      } else if (Array.isArray(d)) {
        msg = d.map((x) => x.msg || JSON.stringify(x)).join(', ');
      } else {
        msg = JSON.stringify(d);
      }
    }
    throw new Error(msg || 'Request failed');
  }
  return data;
}
