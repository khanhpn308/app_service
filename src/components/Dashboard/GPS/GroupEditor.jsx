import React, { useEffect, useState } from 'react';
import { ArrowLeft, Trash2, UserMinus } from 'lucide-react';

import BulkInvitationForm from './BulkInvitationForm';


const STATUS_LABELS = {
  pending: 'Đang chờ',
  accepted: 'Đã tham gia',
  rejected: 'Đã từ chối',
};


const GroupEditor = ({
  group,
  members,
  isLoading,
  isBusy,
  onBack,
  onRename,
  onInviteBulk,
  invitationResults,
  onRemove,
  onDelete,
}) => {
  const [name, setName] = useState(group.name);

  useEffect(() => {
    setName(group.name);
  }, [group.group_id, group.name]);

  const submitRename = async (event) => {
    event.preventDefault();
    await onRename(name.trim());
  };

  return (
    <section aria-labelledby="group-editor-title" className="space-y-4">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onBack}
          className="rounded-md p-2 text-gray-600 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          aria-label="Quay lại danh sách nhóm"
        >
          <ArrowLeft aria-hidden="true" className="h-4 w-4" />
        </button>
        <div className="min-w-0 flex-1">
          <h3 id="group-editor-title" className="truncate text-base font-semibold text-gray-900">
            {group.name}
          </h3>
          <p className="text-xs text-gray-500">Owner: {group.owner_username}</p>
        </div>
        <button
          type="button"
          disabled={isBusy}
          onClick={onDelete}
          className="inline-flex items-center gap-1 rounded-md border border-red-200 px-2.5 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"
        >
          <Trash2 aria-hidden="true" className="h-3.5 w-3.5" />
          Xóa nhóm
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <form onSubmit={submitRename} className="rounded-lg border border-gray-200 p-3">
          <label htmlFor="rename-map-group" className="text-xs font-medium text-gray-700">
            Đổi tên nhóm
          </label>
          <div className="mt-1 flex gap-2">
            <input
              id="rename-map-group"
              required
              maxLength={100}
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="min-w-0 flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
            />
            <button
              type="submit"
              disabled={isBusy || !name.trim()}
              className="rounded-md bg-gray-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
            >
              Lưu tên
            </button>
          </div>
        </form>

        <BulkInvitationForm
          isBusy={isBusy}
          results={invitationResults}
          onSubmit={onInviteBulk}
        />
      </div>

      <div>
        <h4 className="mb-2 text-sm font-semibold text-gray-900">Thành viên và lời mời</h4>
        {isLoading ? (
          <p role="status" className="py-6 text-center text-sm text-gray-500">
            Đang tải thành viên...
          </p>
        ) : (
          <div className="max-h-56 space-y-2 overflow-y-auto">
            {members.map((member) => (
              <div
                key={member.user_id}
                className="flex items-center gap-3 rounded-lg border border-gray-200 p-3"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-gray-900">{member.fullname}</p>
                  <p className="truncate text-xs text-gray-500">@{member.username}</p>
                </div>
                <span className="text-xs text-gray-600">
                  {STATUS_LABELS[member.status] || member.status}
                </span>
                <button
                  type="button"
                  aria-label={`Gỡ ${member.username}`}
                  disabled={isBusy}
                  onClick={() => onRemove(member)}
                  className="rounded-md p-2 text-red-600 hover:bg-red-50 disabled:opacity-50"
                >
                  <UserMinus aria-hidden="true" className="h-4 w-4" />
                </button>
              </div>
            ))}
            {members.length === 0 && (
              <p className="rounded-lg border border-dashed border-gray-300 p-5 text-center text-sm text-gray-500">
                Chưa có lời mời hoặc thành viên.
              </p>
            )}
          </div>
        )}
      </div>
    </section>
  );
};

export default GroupEditor;
