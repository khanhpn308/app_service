import { useEffect, useState } from 'react'

import { listDeletedMaps } from '@/lib/mapsApi'
import { Button } from '@/components/ui/button'

const PAGE_SIZE = 20

const reasonLabels = {
  map_deleted: 'Xóa bản đồ',
  group_deleted: 'Xóa nhóm',
  owner_deleted: 'Xóa chủ sở hữu',
}

function DeletedMapsPanel() {
  const [page, setPage] = useState(0)
  const [result, setResult] = useState({
    data: [],
    total: 0,
    limit: PAGE_SIZE,
    offset: 0,
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    listDeletedMaps({ limit: PAGE_SIZE, offset: page * PAGE_SIZE })
      .then((nextResult) => {
        if (active) setResult(nextResult)
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError.message || 'Không thể tải lịch sử bản đồ.')
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [page])

  if (loading) {
    return (
      <div role="status" className="py-10 text-center text-sm text-slate-500">
        Đang tải lịch sử...
      </div>
    )
  }

  if (error) {
    return (
      <p role="alert" className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
        {error}
      </p>
    )
  }

  return (
    <section aria-labelledby="deleted-maps-title" className="space-y-4">
      <div>
        <h3 id="deleted-maps-title" className="font-semibold text-slate-900">
          Bản đồ đã xóa
        </h3>
        <p className="text-sm text-slate-500">
          Nhật ký chỉ chứa metadata; nội dung ảnh không được tải về màn hình này.
        </p>
      </div>

      <div className="overflow-x-auto rounded-md border">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-3 py-2">Location</th>
              <th className="px-3 py-2">Nhóm</th>
              <th className="px-3 py-2">Chủ sở hữu</th>
              <th className="px-3 py-2">Người xóa</th>
              <th className="px-3 py-2">Lý do</th>
              <th className="px-3 py-2">Thời điểm</th>
            </tr>
          </thead>
          <tbody>
            {result.data.map((map) => (
              <tr key={map.location_id} className="border-t">
                <td className="px-3 py-2 font-medium text-slate-900">{map.location}</td>
                <td className="px-3 py-2">{map.group_name_snapshot}</td>
                <td className="px-3 py-2">{map.owner_username_snapshot}</td>
                <td className="px-3 py-2">{map.deleted_by_username_snapshot}</td>
                <td className="px-3 py-2">
                  {reasonLabels[map.delete_reason] || map.delete_reason}
                </td>
                <td className="px-3 py-2">
                  {new Date(map.deleted_at).toLocaleString('vi-VN')}
                </td>
              </tr>
            ))}
            {result.data.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-8 text-center text-slate-500">
                  Chưa có bản đồ nào bị xóa.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-500">Tổng cộng {result.total} bản ghi</span>
        <div className="flex gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={page === 0}
            onClick={() => setPage((current) => current - 1)}
          >
            Trang trước
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={(page + 1) * PAGE_SIZE >= result.total}
            onClick={() => setPage((current) => current + 1)}
          >
            Trang sau
          </Button>
        </div>
      </div>
    </section>
  )
}

export default DeletedMapsPanel
