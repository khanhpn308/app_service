import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import MapGroupManagerDialog from './MapGroupManagerDialog';
import {
  createMapGroup,
  inviteMapGroupMember,
  listMapGroupMembers,
  listMapGroups,
  listMyMapGroupInvitations,
  removeMapGroupMember,
  renameMapGroup,
  respondToMapGroupInvitation,
} from '../../../lib/mapGroupsApi';


let currentUser = { user_id: 1, username: 'owner', role: 'user' };

vi.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({ user: currentUser }),
}));

vi.mock('../../../lib/mapGroupsApi', () => ({
  createMapGroup: vi.fn(),
  deleteMapGroup: vi.fn(),
  inviteMapGroupMember: vi.fn(),
  listMapGroupMembers: vi.fn(),
  listMapGroups: vi.fn(),
  listMyMapGroupInvitations: vi.fn(),
  removeMapGroupMember: vi.fn(),
  renameMapGroup: vi.fn(),
  respondToMapGroupInvitation: vi.fn(),
}));


const ownerGroup = {
  group_id: 1,
  name: 'Factory A',
  owner_user_id: 1,
  owner_username: 'owner',
  created_by_user_id: 1,
  created_at: '2026-07-22T10:00:00',
  updated_at: '2026-07-22T10:00:00',
  access_role: 'owner',
  can_manage: true,
};

const memberGroup = {
  ...ownerGroup,
  group_id: 2,
  name: 'Shared Floor',
  owner_user_id: 9,
  owner_username: 'other-owner',
  access_role: 'member',
  can_manage: false,
};

const pendingInvitation = {
  group_id: 3,
  group_name: 'Warehouse',
  owner_username: 'warehouse-owner',
  status: 'pending',
  invited_at: '2026-07-22T10:00:00',
  responded_at: null,
};


describe('MapGroupManagerDialog', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    currentUser = { user_id: 1, username: 'owner', role: 'user' };
    listMapGroups.mockResolvedValue([ownerGroup, memberGroup]);
    listMyMapGroupInvitations.mockResolvedValue([pendingInvitation]);
    listMapGroupMembers.mockResolvedValue([
      {
        group_id: 1,
        user_id: 7,
        username: 'member',
        fullname: 'Member User',
        status: 'accepted',
        invited_by_user_id: 1,
        invited_at: '2026-07-22T10:00:00',
        responded_at: '2026-07-22T10:05:00',
      },
    ]);
    createMapGroup.mockResolvedValue(ownerGroup);
    renameMapGroup.mockResolvedValue({ ...ownerGroup, name: 'Renamed' });
    inviteMapGroupMember.mockResolvedValue({});
    removeMapGroupMember.mockResolvedValue(null);
    respondToMapGroupInvitation.mockResolvedValue({});
  });

  it('loads visible groups and marks accepted-member groups read-only', async () => {
    const user = userEvent.setup();
    render(<MapGroupManagerDialog />);

    await user.click(screen.getByRole('button', { name: 'Quản lý nhóm' }));

    expect(await screen.findByText('Factory A')).toBeTruthy();
    expect(screen.getByText('Shared Floor')).toBeTruthy();
    expect(screen.getByText('Chỉ xem')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Lời mời \(1\)/ })).toBeTruthy();
  });

  it('creates a group and lets the owner rename, invite and remove members', async () => {
    const user = userEvent.setup();
    render(<MapGroupManagerDialog />);
    await user.click(screen.getByRole('button', { name: 'Quản lý nhóm' }));
    await screen.findByText('Factory A');

    await user.type(screen.getByLabelText('Tên nhóm mới'), 'New Group');
    await user.click(screen.getByRole('button', { name: 'Tạo nhóm' }));
    expect(createMapGroup).toHaveBeenCalledWith({ name: 'New Group' });

    await user.click(screen.getByRole('button', { name: /Quản lý Factory A/ }));
    expect(await screen.findByText('Member User')).toBeTruthy();

    const renameInput = screen.getByLabelText('Đổi tên nhóm');
    fireEvent.change(renameInput, { target: { value: 'Renamed' } });
    await user.click(screen.getByRole('button', { name: 'Lưu tên' }));
    expect(renameMapGroup).toHaveBeenCalledWith(1, 'Renamed');

    await user.type(screen.getByLabelText('Username cần mời'), 'new-member');
    await user.click(screen.getByRole('button', { name: 'Gửi lời mời' }));
    expect(inviteMapGroupMember).toHaveBeenCalledWith(1, 'new-member');

    await user.click(screen.getByRole('button', { name: 'Gỡ member' }));
    expect(removeMapGroupMember).toHaveBeenCalledWith(1, 7);
  });

  it('shows owner username for admin creation and accepts an invitation', async () => {
    currentUser = { user_id: 99, username: 'admin', role: 'admin' };
    const user = userEvent.setup();
    render(<MapGroupManagerDialog />);
    await user.click(screen.getByRole('button', { name: 'Quản lý nhóm' }));
    await screen.findByText('Factory A');

    expect(screen.getByLabelText('Username owner')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: /Lời mời \(1\)/ }));
    await user.click(screen.getByRole('button', { name: 'Chấp nhận Warehouse' }));

    expect(respondToMapGroupInvitation).toHaveBeenCalledWith(3, 'accepted');
    await waitFor(() => {
      expect(listMyMapGroupInvitations).toHaveBeenCalledTimes(2);
    });
  });

  it('renders a recoverable error when loading fails', async () => {
    listMapGroups.mockRejectedValueOnce(new Error('Mất kết nối'));
    const user = userEvent.setup();
    render(<MapGroupManagerDialog />);

    await user.click(screen.getByRole('button', { name: 'Quản lý nhóm' }));

    expect((await screen.findByRole('alert')).textContent).toContain('Mất kết nối');
    expect(screen.getByRole('button', { name: 'Thử lại' })).toBeTruthy();
  });
});
