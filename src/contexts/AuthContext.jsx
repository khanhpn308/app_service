/**
 * Context React cho trạng thái đăng nhập.
 *
 * Lưu ý:
 * - Token JWT: `localStorage` key `iot_token` — gửi kèm header `Authorization: Bearer` qua `apiFetch`.
 * - Profile cache: `iot_user` (chuỗi JSON) — dùng hiển thị nhanh; `refreshUser` gọi `/api/auth/me` để đồng bộ server.
 * - `loading`: true trong lần đầu `loadSession` — route guard chờ trước khi redirect `/login`.
 *
 * Hook `useAuth` bắt buộc dùng bên trong `AuthProvider`.
 */
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../lib/api';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  /** Đọc token; nếu có thì xác thực với backend; nếu lỗi thì xóa token và user. */
  const loadSession = useCallback(async () => {
    const token = localStorage.getItem('iot_token');
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await apiFetch('/api/auth/me');
      setUser(me);
    } catch {
      localStorage.removeItem('iot_token');
      localStorage.removeItem('iot_user');
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  /** POST `/api/auth/login`; lưu token + user; `skipAuth` vì chưa có Bearer. */
  const login = async (username, password) => {
    localStorage.removeItem('iot_token');
    const data = await apiFetch('/api/auth/login', {
      method: 'POST',
      skipAuth: true,
      body: JSON.stringify({ username, password }),
    });
    localStorage.setItem('iot_token', data.access_token);
    localStorage.setItem('iot_user', JSON.stringify(data.user));
    setUser(data.user);
    return { success: true, user: data.user };
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('iot_token');
    localStorage.removeItem('iot_user');
  };

  /** RBAC phía UI — backend vẫn phải kiểm tra lại. */
  const isAdmin = () => user?.role === 'admin';

  const value = {
    user,
    login,
    logout,
    isAdmin,
    loading,
    refreshUser: loadSession,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
