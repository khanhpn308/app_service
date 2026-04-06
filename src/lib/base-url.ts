/**
 * Base URL của ứng dụng Vite (import.meta.env.BASE_URL), bỏ dấu `/` cuối.
 * Dùng khi cần đường dẫn tuyệt đối tới asset public (hiếm khi cần so với `api.js`).
 */
export const baseUrl = import.meta.env.BASE_URL.replace(/\/$/, '');
