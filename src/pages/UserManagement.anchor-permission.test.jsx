// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import UserManagement from './UserManagement';
import { apiFetch } from '../lib/api';

vi.mock('../lib/api', () => ({ apiFetch: vi.fn() }));
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { user_id: 99, username: 'root', role: 'admin' } }),
}));
vi.mock('../components/AssignDeviceModal', () => ({ default: () => null }));

const regularUser = {
  user_id: 1,
  username: 'owner',
  fullname: 'Map Owner',
  role: 'user',
  status: 'active',
  can_config_anchor: 'no',
  creat_at: '2026-01-01',
  expired_at: '2099-01-01',
  remaining_days: 100,
  authorized_devices: [],
};

const adminUser = {
  ...regularUser,
  user_id: 2,
  username: 'admin',
  fullname: 'System Admin',
  role: 'admin',
};

globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

describe('UserManagement anchor permission', () => {
  beforeEach(() => {
    apiFetch.mockReset();
    apiFetch.mockImplementation(async (path) => {
      if (path === '/api/users') return [regularUser, adminUser];
      return {};
    });
  });

  afterEach(cleanup);

  it('shows an editable switch for regular users and a fixed admin explanation', async () => {
    render(<UserManagement />);

    const permissionSwitch = await screen.findByRole('switch', {
      name: 'Cho phép @owner cấu hình Anchor',
    });
    expect(permissionSwitch.getAttribute('aria-checked')).toBe('false');
    expect(screen.getByText('Admin luôn có quyền cấu hình Anchor')).toBeTruthy();
    expect(screen.getAllByRole('switch')).toHaveLength(1);
  });

  it('sends the selected permission when registering a regular user', async () => {
    const user = userEvent.setup();
    render(<UserManagement />);

    await screen.findByText('Map Owner');
    await user.click(screen.getByRole('button', { name: /Đăng ký tài khoản/i }));
    const dialog = screen.getByRole('dialog', { name: 'Đăng ký tài khoản' });
    const permissionSwitch = within(dialog).getByRole('switch', {
      name: 'Cho phép cấu hình Anchor',
    });
    expect(permissionSwitch.getAttribute('aria-checked')).toBe('false');

    const field = (label) => within(dialog).getByText(label).parentElement.querySelector('input');
    await user.type(field('Tên đăng nhập'), 'new-owner');
    await user.type(field('Họ và tên'), 'New Owner');
    await user.type(field('CCCD (12 số)'), '000000000003');
    await user.type(field('Mật khẩu'), 'secret123');
    await user.type(field('Xác nhận mật khẩu'), 'secret123');
    await user.click(permissionSwitch);
    await user.click(within(dialog).getByRole('button', { name: 'Tạo tài khoản' }));

    await waitFor(() => {
      const registerCall = apiFetch.mock.calls.find(([path]) => path === '/api/auth/register');
      expect(registerCall).toBeTruthy();
      expect(JSON.parse(registerCall[1].body).can_config_anchor).toBe('yes');
    });
  });

  it('rolls back the user switch and reports the API error', async () => {
    const user = userEvent.setup();
    apiFetch.mockImplementation(async (path) => {
      if (path === '/api/users') return [regularUser];
      if (path === '/api/users/1/anchor-permission') {
        throw new Error('Không thể cập nhật quyền Anchor');
      }
      return {};
    });
    render(<UserManagement />);

    const permissionSwitch = await screen.findByRole('switch', {
      name: 'Cho phép @owner cấu hình Anchor',
    });
    await user.click(permissionSwitch);

    await waitFor(() =>
      expect(permissionSwitch.getAttribute('aria-checked')).toBe('false')
    );
    expect(screen.getByRole('alert').textContent).toContain('Không thể cập nhật quyền Anchor');
    expect(apiFetch).toHaveBeenCalledWith('/api/users/1/anchor-permission', {
      method: 'PATCH',
      body: JSON.stringify({ can_config_anchor: 'yes' }),
    });
  });
});
