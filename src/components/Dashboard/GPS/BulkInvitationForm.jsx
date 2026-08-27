import React, { useState } from 'react'
import { UserPlus } from 'lucide-react'

const RESULT_LABELS = {
  invited: 'Đã mời',
  duplicate_input: 'Username bị lặp',
  user_not_found: 'Không tìm thấy người dùng',
  inactive_user: 'Tài khoản không còn hiệu lực',
  already_member: 'Đã là thành viên hoặc đã được mời',
  self_invite: 'Không thể tự mời',
}

function parseUsernames(value) {
  return value.split(/[\n,]+/).map((item) => item.trim()).filter(Boolean)
}

export default function BulkInvitationForm({ isBusy, results, onSubmit }) {
  const [value, setValue] = useState('')

  async function submit(event) {
    event.preventDefault()
    const usernames = parseUsernames(value)
    if (!usernames.length || usernames.length > 50) return
    const succeeded = await onSubmit(usernames)
    if (succeeded) setValue('')
  }

  const count = parseUsernames(value).length
  return (
    <div className="space-y-3 rounded-lg border border-gray-200 p-3 md:col-span-2">
      <form onSubmit={submit}>
        <label htmlFor="invite-map-members" className="text-xs font-medium text-gray-700">
          Usernames cần mời
        </label>
        <textarea
          id="invite-map-members"
          rows={3}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Mỗi username một dòng hoặc ngăn cách bằng dấu phẩy"
          className="mt-1 w-full resize-y rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
        />
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
          <span className={`text-xs ${count > 50 ? 'text-red-600' : 'text-gray-500'}`}>
            {count}/50 username
          </span>
          <button
            type="submit"
            disabled={isBusy || count === 0 || count > 50}
            className="inline-flex items-center gap-1 rounded-md bg-blue-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
          >
            <UserPlus aria-hidden="true" className="h-3.5 w-3.5" />
            Gửi lời mời hàng loạt
          </button>
        </div>
      </form>
      {results?.length > 0 && (
        <div aria-live="polite" className="max-h-40 space-y-1 overflow-y-auto border-t pt-2">
          {results.map((result, index) => (
            <div key={`${result.username}-${index}`} className="flex items-start justify-between gap-3 text-xs">
              <span className="font-medium text-gray-800">@{result.username}</span>
              <span className={result.status === 'invited' ? 'text-emerald-700' : 'text-red-700'}>
                {result.message || RESULT_LABELS[result.code] || RESULT_LABELS[result.status]}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
