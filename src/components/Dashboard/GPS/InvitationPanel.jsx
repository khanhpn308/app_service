import React from 'react';
import { Check, X } from 'lucide-react';


const InvitationPanel = ({ invitations, isBusy, onRespond }) => (
  <section aria-labelledby="invitation-title">
    <h3 id="invitation-title" className="mb-3 text-sm font-semibold text-gray-900">
      Lời mời đang chờ
    </h3>
    <div className="max-h-80 space-y-2 overflow-y-auto">
      {invitations.map((invitation) => (
        <article
          key={invitation.group_id}
          className="flex flex-col gap-3 rounded-lg border border-gray-200 p-3 sm:flex-row sm:items-center"
        >
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-gray-900">
              {invitation.group_name}
            </p>
            <p className="truncate text-xs text-gray-500">
              Mời bởi owner @{invitation.owner_username}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              aria-label={`Từ chối ${invitation.group_name}`}
              disabled={isBusy}
              onClick={() => onRespond(invitation, 'rejected')}
              className="inline-flex items-center gap-1 rounded-md border border-gray-300 px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              <X aria-hidden="true" className="h-3.5 w-3.5" />
              Từ chối
            </button>
            <button
              type="button"
              aria-label={`Chấp nhận ${invitation.group_name}`}
              disabled={isBusy}
              onClick={() => onRespond(invitation, 'accepted')}
              className="inline-flex items-center gap-1 rounded-md bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              <Check aria-hidden="true" className="h-3.5 w-3.5" />
              Chấp nhận
            </button>
          </div>
        </article>
      ))}
      {invitations.length === 0 && (
        <p className="rounded-lg border border-dashed border-gray-300 p-8 text-center text-sm text-gray-500">
          Không có lời mời đang chờ.
        </p>
      )}
    </div>
  </section>
);

export default InvitationPanel;
