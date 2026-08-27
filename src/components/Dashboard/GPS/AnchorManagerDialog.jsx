import React, { useEffect, useMemo, useState } from 'react'
import { ListFilter } from 'lucide-react'

import { manageAnchors } from '@/lib/anchorsApi'
import { listGroupMaps } from '@/lib/mapsApi'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'

const PAGE_SIZE = 25

export default function AnchorManagerDialog({ groups, onSelect }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [groupId, setGroupId] = useState('')
  const [locationId, setLocationId] = useState('')
  const [maps, setMaps] = useState([])
  const [page, setPage] = useState(0)
  const [result, setResult] = useState({ data: [], total: 0 })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDebouncedQuery(query.trim())
      setPage(0)
    }, 300)
    return () => window.clearTimeout(timeout)
  }, [query])

  useEffect(() => {
    let active = true
    setMaps([])
    setLocationId('')
    if (!groupId) return () => { active = false }
    listGroupMaps(Number(groupId))
      .then((nextMaps) => { if (active) setMaps(nextMaps) })
      .catch((requestError) => { if (active) setError(requestError.message || 'Không thể tải map.') })
    return () => { active = false }
  }, [groupId])

  useEffect(() => {
    if (!open) return () => {}
    const controller = new AbortController()
    setLoading(true)
    setError('')
    manageAnchors({
      q: debouncedQuery,
      groupId: groupId ? Number(groupId) : undefined,
      locationId: locationId ? Number(locationId) : undefined,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    }, { signal: controller.signal })
      .then(setResult)
      .catch((requestError) => {
        if (requestError.name !== 'AbortError') setError(requestError.message || 'Không thể tải Anchor.')
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [debouncedQuery, groupId, locationId, open, page])

  const groupNames = useMemo(
    () => new Map(groups.map((group) => [group.group_id, group.name])),
    [groups],
  )
  const pageCount = Math.max(1, Math.ceil(result.total / PAGE_SIZE))

  function changeOpen(nextOpen) {
    setOpen(nextOpen)
    if (!nextOpen) {
      setQuery('')
      setDebouncedQuery('')
      setGroupId('')
      setLocationId('')
      setPage(0)
      setError('')
    }
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" className="gap-2">
          <ListFilter className="h-4 w-4" aria-hidden="true" />
          Quản lý Anchor
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-6xl">
        <DialogHeader>
          <DialogTitle>Quản lý Anchor</DialogTitle>
          <DialogDescription>Tìm Anchor có quyền cấu hình và mở trực tiếp trên đúng bản đồ.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-xs font-medium text-gray-700">
            Tìm Anchor
            <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tên, MAC Address hoặc DB ID" className="mt-1 w-full rounded-md border px-3 py-2 text-sm" />
          </label>
          <label className="text-xs font-medium text-gray-700">
            Lọc theo nhóm
            <select value={groupId} onChange={(event) => { setGroupId(event.target.value); setLocationId(''); setPage(0) }} className="mt-1 w-full rounded-md border bg-white px-3 py-2 text-sm text-gray-900">
              <option value="">Tất cả nhóm</option>
              {groups.map((group) => <option key={group.group_id} value={group.group_id}>{group.name}</option>)}
            </select>
          </label>
          <label className="text-xs font-medium text-gray-700">
            Lọc theo map
            <select disabled={!groupId} value={locationId} onChange={(event) => { setLocationId(event.target.value); setPage(0) }} className="mt-1 w-full rounded-md border bg-white px-3 py-2 text-sm text-gray-900 disabled:bg-gray-100">
              <option value="">Tất cả map</option>
              {maps.map((map) => <option key={map.location_id} value={map.location_id}>{map.location}</option>)}
            </select>
          </label>
        </div>
        {error && <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <div className="overflow-x-auto rounded-lg border">
          <table className="min-w-[920px] w-full text-left text-sm">
            <thead className="bg-gray-50 text-xs text-gray-600"><tr><th className="p-2">Anchor</th><th className="p-2">MAC Address</th><th className="p-2">Nhóm / Map</th><th className="p-2">X</th><th className="p-2">Y</th><th className="p-2">Z</th><th className="p-2">Cập nhật</th></tr></thead>
            <tbody>
              {result.data.map((anchor) => (
                <tr key={anchor.anchor_id} className="border-t hover:bg-blue-50">
                  <td className="p-2"><button type="button" aria-label={`Cấu hình Anchor ${anchor.name}`} onClick={() => { setOpen(false); onSelect(anchor) }} className="font-semibold text-blue-700 hover:underline">{anchor.name}</button><span className="ml-2 text-xs text-gray-500">#{anchor.anchor_id}</span></td>
                  <td className="p-2 font-mono text-xs">{anchor.mac_address || 'Chưa cấu hình'}</td><td className="p-2">{groupNames.get(anchor.group_id) || `#${anchor.group_id}`} / {anchor.location}</td>
                  <td className="p-2">{anchor.x}</td><td className="p-2">{anchor.y}</td><td className="p-2">{anchor.z}</td><td className="p-2 text-xs text-gray-500">{new Date(anchor.updated_at).toLocaleString('vi-VN')}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && result.data.length === 0 && <p role="status" className="p-8 text-center text-sm text-gray-500">Không tìm thấy Anchor.</p>}
          {loading && <p role="status" className="p-8 text-center text-sm text-gray-500">Đang tải Anchor...</p>}
        </div>
        <div className="flex items-center justify-between text-sm"><span>Trang {page + 1}/{pageCount} · {result.total} Anchor</span><div className="flex gap-2"><Button type="button" variant="outline" disabled={page === 0 || loading} onClick={() => setPage((value) => value - 1)}>Trang trước</Button><Button type="button" variant="outline" disabled={page + 1 >= pageCount || loading} onClick={() => setPage((value) => value + 1)}>Trang sau</Button></div></div>
      </DialogContent>
    </Dialog>
  )
}
