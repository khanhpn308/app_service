import React, { useState } from 'react';
import { Plus, Settings2 } from 'lucide-react';


const GroupListPanel = ({
  groups,
  isAdmin,
  isBusy,
  onCreate,
  onManage,
}) => {
  const [name, setName] = useState('');
  const [ownerUsername, setOwnerUsername] = useState('');

  const handleCreate = async (event) => {
    event.preventDefault();
    const input = { name: name.trim() };
    if (isAdmin && ownerUsername.trim()) {
      input.owner_username = ownerUsername.trim();
    }
    await onCreate(input);
    setName('');
    setOwnerUsername('');
  };

  return (
    <div className="grid min-h-0 gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
      <section aria-labelledby="group-list-title" className="min-w-0">
        <div className="mb-3 flex items-center justify-between">
          <h3 id="group-list-title" className="text-sm font-semibold text-gray-900">
            Nhóm có thể truy cập
          </h3>
          <span className="text-xs text-gray-500">{groups.length} nhóm</span>
        </div>
        <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
          {groups.map((group) => (
            <article
              key={group.group_id}
              className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-3"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-gray-900">{group.name}</p>
                <p className="truncate text-xs text-gray-500">
                  Owner: {group.owner_username}
                </p>
              </div>
              {group.can_manage ? (
                <button
                  type="button"
                  aria-label={`Quản lý ${group.name}`}
                  onClick={() => onManage(group)}
                  className="inline-flex items-center gap-1 rounded-md border border-blue-200 px-2.5 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <Settings2 aria-hidden="true" className="h-3.5 w-3.5" />
                  Quản lý
                </button>
              ) : (
                <span className="rounded-full bg-gray-100 px-2 py-1 text-[11px] font-medium text-gray-600">
                  Chỉ xem
                </span>
              )}
            </article>
          ))}
          {groups.length === 0 && (
            <p className="rounded-lg border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
              Chưa có nhóm bản đồ nào.
            </p>
          )}
        </div>
      </section>

      <form
        onSubmit={handleCreate}
        className="rounded-lg border border-gray-200 bg-gray-50 p-3"
      >
        <h3 className="mb-3 text-sm font-semibold text-gray-900">Tạo nhóm</h3>
        <label htmlFor="new-map-group-name" className="text-xs font-medium text-gray-700">
          Tên nhóm mới
        </label>
        <input
          id="new-map-group-name"
          required
          maxLength={100}
          value={name}
          onChange={(event) => setName(event.target.value)}
          className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
        />
        {isAdmin && (
          <>
            <label
              htmlFor="new-map-group-owner"
              className="mt-3 block text-xs font-medium text-gray-700"
            >
              Username owner
            </label>
            <input
              id="new-map-group-owner"
              maxLength={45}
              value={ownerUsername}
              onChange={(event) => setOwnerUsername(event.target.value)}
              placeholder="Để trống = tài khoản admin"
              className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
            />
          </>
        )}
        <button
          type="submit"
          disabled={isBusy || !name.trim()}
          className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus aria-hidden="true" className="h-4 w-4" />
          Tạo nhóm
        </button>
      </form>
    </div>
  );
};

export default GroupListPanel;
