import React, { useCallback, useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { getAnchorConfigStatus, resyncAnchorConfig } from '@/lib/anchorsApi'

const labels = {
  synced: 'Đã đồng bộ',
  partial: 'Một phần',
  pending: 'Đang chờ',
  error: 'Lỗi',
  no_gateway: 'Không có Gateway',
}

const colors = {
  synced: 'border-emerald-300 bg-emerald-50 text-emerald-700',
  partial: 'border-amber-300 bg-amber-50 text-amber-700',
  pending: 'border-blue-300 bg-blue-50 text-blue-700',
  error: 'border-red-300 bg-red-50 text-red-700',
  no_gateway: 'border-gray-300 bg-gray-50 text-gray-700',
}

export default function AnchorSyncStatus({ locationId, enabled, onPermissionRevoked }) {
  const [status, setStatus] = useState(null)
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [busyGatewayId, setBusyGatewayId] = useState(null)

  const refresh = useCallback(async (signal) => {
    if (!enabled || !locationId) return
    try {
      const next = await getAnchorConfigStatus(locationId, signal ? { signal } : {})
      setStatus(next)
      setMessage('')
    } catch (error) {
      if (error.name === 'AbortError') return
      if (error.status === 403) onPermissionRevoked?.()
      setMessage(error.message || 'Không thể tải trạng thái đồng bộ Anchor.')
    }
  }, [enabled, locationId, onPermissionRevoked])

  useEffect(() => {
    setStatus(null)
    setOpen(false)
    if (!enabled || !locationId) return undefined
    const controller = new AbortController()
    refresh(controller.signal)
    const timer = window.setInterval(() => refresh(), 5000)
    return () => {
      controller.abort()
      window.clearInterval(timer)
    }
  }, [enabled, locationId, refresh])

  if (!enabled || !locationId) return null
  const aggregate = status?.aggregate || 'pending'
  const label = labels[aggregate] || aggregate

  const handleResync = async (gateway) => {
    setBusyGatewayId(gateway.gateway_id)
    setMessage('')
    try {
      const result = await resyncAnchorConfig(locationId, gateway.gateway_id)
      await refresh()
      setMessage(`Đã tạo revision ${result.config_revision} cho Gateway ${gateway.gateway_id}.`)
    } catch (error) {
      if (error.status === 403) onPermissionRevoked?.()
      setMessage(error.message || 'Không thể gửi lại cấu hình Anchor.')
    } finally {
      setBusyGatewayId(null)
    }
  }

  return (
    <div className="w-full">
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild>
          <Button
            type="button"
            variant="outline"
            aria-label={`Đồng bộ Anchor: ${label}`}
            className={`w-full justify-start ${colors[aggregate]}`}
          >
            {label}{status?.revision ? ` · r${status.revision}` : ''}
          </Button>
        </DialogTrigger>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Đồng bộ Anchor</DialogTitle>
            <DialogDescription>
              {status?.anchor_count ?? 0} Anchor · revision {status?.revision ?? '—'}
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-64 space-y-2 overflow-y-auto">
            {(status?.gateways || []).map((gateway) => (
              <article key={gateway.gateway_id} className="rounded-lg border p-3 text-sm">
                <div className="flex justify-between gap-3 font-medium">
                  <span>{gateway.devicename || 'Gateway'} ({gateway.gateway_id})</span>
                  <span className={gateway.online ? 'text-emerald-700' : 'text-gray-500'}>{gateway.online ? 'Online' : 'Offline'}</span>
                </div>
                <p className="mt-1 text-xs text-gray-600">Trạng thái: {gateway.delivery_status} · target r{gateway.target_revision ?? '—'} · applied r{gateway.applied_revision ?? '—'}</p>
                {gateway.last_seen_at && <p className="text-xs text-gray-500">Last seen: {new Date(gateway.last_seen_at).toLocaleString()}</p>}
                {gateway.error && <p role="alert" className="mt-1 text-xs text-red-700">{gateway.error}</p>}
                <div className="mt-3 flex justify-end">
                  <Button
                    type="button"
                    size="sm"
                    aria-label={`Gửi lại cấu hình cho ${gateway.devicename || 'Gateway'} (${gateway.gateway_id})`}
                    onClick={() => handleResync(gateway)}
                    disabled={busyGatewayId === gateway.gateway_id}
                  >
                    {busyGatewayId === gateway.gateway_id ? 'Đang gửi…' : 'Gửi lại cấu hình'}
                  </Button>
                </div>
              </article>
            ))}
            {status && status.gateways.length === 0 && <p className="text-sm text-gray-500">Không có Gateway active khớp location.</p>}
          </div>
          {message && <p aria-live="polite" className="mt-3 text-xs text-gray-700">{message}</p>}
        </DialogContent>
      </Dialog>
    </div>
  )
}
