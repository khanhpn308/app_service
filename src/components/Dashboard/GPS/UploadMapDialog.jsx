import { useEffect, useMemo, useState } from 'react'
import { Plus, UploadCloud } from 'lucide-react'

import { uploadGroupMap } from '@/lib/mapsApi'
import { validateMapFile } from '@/lib/mapFileValidation'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

function UploadMapDialog({ groups, defaultGroupId, onUploaded }) {
  const manageableGroups = useMemo(
    () => (groups || []).filter((group) => group.can_manage),
    [groups],
  )
  const [open, setOpen] = useState(false)
  const [groupId, setGroupId] = useState('')
  const [location, setLocation] = useState('')
  const [file, setFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    const preferred = manageableGroups.find(
      (group) => group.group_id === Number(defaultGroupId),
    )
    setGroupId(String(preferred?.group_id ?? manageableGroups[0]?.group_id ?? ''))
  }, [defaultGroupId, manageableGroups, open])

  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    },
    [previewUrl],
  )

  const resetFile = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setPreviewUrl('')
    setFile(null)
  }

  const handleOpenChange = (nextOpen) => {
    setOpen(nextOpen)
    if (!nextOpen) {
      resetFile()
      setLocation('')
      setError('')
      setBusy(false)
    }
  }

  const acceptFile = async (nextFile) => {
    resetFile()
    setError('')
    if (!nextFile) return
    try {
      await validateMapFile(nextFile)
      setFile(nextFile)
      setPreviewUrl(URL.createObjectURL(nextFile))
    } catch (validationError) {
      setError(validationError.message || 'Ảnh không hợp lệ.')
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    const normalizedLocation = location.trim()
    if (!groupId) {
      setError('Bạn chưa có nhóm bản đồ có quyền quản lý.')
      return
    }
    if (!normalizedLocation) {
      setError('Vui lòng nhập location trùng với gateway.')
      return
    }
    if (!file) {
      setError('Vui lòng chọn ảnh WebP hợp lệ.')
      return
    }

    setBusy(true)
    setError('')
    try {
      const uploaded = await uploadGroupMap(Number(groupId), {
        location: normalizedLocation,
        file,
      })
      onUploaded?.(uploaded)
      handleOpenChange(false)
    } catch (requestError) {
      setError(requestError.message || 'Không thể tải ảnh lên.')
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button
          type="button"
          className="gap-2"
          disabled={manageableGroups.length === 0}
          title={
            manageableGroups.length === 0
              ? 'Bạn cần tạo hoặc sở hữu một nhóm bản đồ'
              : undefined
          }
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          Thêm bản đồ
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Thêm ảnh bản đồ</DialogTitle>
          <DialogDescription>
            Location phải trùng chính xác với location mà gateway gửi lên.
          </DialogDescription>
        </DialogHeader>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-1">
            <label htmlFor="upload-map-group" className="text-sm font-medium">
              Nhóm bản đồ
            </label>
            <select
              id="upload-map-group"
              value={groupId}
              onChange={(event) => setGroupId(event.target.value)}
              className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
            >
              {manageableGroups.map((group) => (
                <option key={group.group_id} value={group.group_id}>
                  {group.name}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label htmlFor="upload-map-location" className="text-sm font-medium">
              Location gateway
            </label>
            <input
              id="upload-map-location"
              value={location}
              maxLength={255}
              onChange={(event) => setLocation(event.target.value)}
              placeholder="Ví dụ: FLOOR_1"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>

          <label
            htmlFor="upload-map-file"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault()
              acceptFile(event.dataTransfer.files?.[0])
            }}
            className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed border-blue-200 bg-blue-50/50 p-6 text-center hover:border-blue-400"
          >
            <UploadCloud className="h-8 w-8 text-blue-600" aria-hidden="true" />
            <span className="text-sm font-medium text-slate-700">
              Kéo thả ảnh vào đây hoặc chọn từ máy
            </span>
            <span className="text-xs text-slate-500">
              WebP tĩnh · 800×1–8000 px · tối đa 5 MB
            </span>
            <input
              id="upload-map-file"
              type="file"
              accept=".webp,image/webp"
              className="sr-only"
              aria-label="Chọn ảnh WebP"
              onChange={(event) => acceptFile(event.target.files?.[0])}
            />
          </label>

          {previewUrl && (
            <img
              src={previewUrl}
              alt="Xem trước bản đồ"
              className="max-h-52 w-full rounded-md border object-contain"
            />
          )}

          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => handleOpenChange(false)}
            >
              Hủy
            </Button>
            <Button type="submit" disabled={busy || !file}>
              {busy ? 'Đang tải...' : 'Tải ảnh lên'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default UploadMapDialog
