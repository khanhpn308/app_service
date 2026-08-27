import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Activity, Clock3, PackageCheck, PackageX, Trash2 } from 'lucide-react'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '../components/ui/alert-dialog'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { apiFetch } from '../lib/api'
import { openWebSocket } from '../lib/wsUrl'

const EMPTY_SUMMARY = {
  total_payload: 0,
  current_payload: null,
  total_missing_payload: 0,
}

function StatCard({ title, icon: Icon, children }) {
  return (
    <Card data-testid="ping-stat-card" className="min-w-0">
      <CardHeader className="grid-cols-[1fr_auto]">
        <CardTitle>{title}</CardTitle>
        <Icon aria-hidden="true" className="h-5 w-5 text-primary" />
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

export default function Ping() {
  const [devices, setDevices] = useState([])
  const [selectedDeviceId, setSelectedDeviceId] = useState('')
  const [summary, setSummary] = useState(EMPTY_SUMMARY)
  const [devicesLoading, setDevicesLoading] = useState(true)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [error, setError] = useState('')
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const mountedRef = useRef(false)
  const selectedDeviceIdRef = useRef('')
  const summaryRequestsRef = useRef(new Map())

  selectedDeviceIdRef.current = selectedDeviceId

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  const refreshSummary = useCallback(async (deviceId) => {
    if (!deviceId) return
    const requests = summaryRequestsRef.current
    const requestState = requests.get(deviceId) ?? { inFlight: false, queued: false }
    requests.set(deviceId, requestState)
    if (requestState.inFlight) {
      requestState.queued = true
      return
    }

    requestState.inFlight = true
    if (mountedRef.current && selectedDeviceIdRef.current === deviceId) {
      setSummaryLoading(true)
      setError('')
    }
    try {
      const nextSummary = await apiFetch(`/api/pings/${deviceId}/summary`)
      if (mountedRef.current && selectedDeviceIdRef.current === deviceId) {
        setSummary(nextSummary)
      }
    } catch (requestError) {
      if (mountedRef.current && selectedDeviceIdRef.current === deviceId) {
        setError(requestError.message || 'Không tải được thống kê ping')
      }
    } finally {
      requestState.inFlight = false
      if (mountedRef.current && selectedDeviceIdRef.current === deviceId) {
        setSummaryLoading(false)
      }
      if (requestState.queued) {
        requestState.queued = false
        if (mountedRef.current && selectedDeviceIdRef.current === deviceId) {
          void refreshSummary(deviceId)
        }
      }
    }
  }, [])

  useEffect(() => {
    let active = true
    async function loadDevices() {
      setDevicesLoading(true)
      setError('')
      try {
        const rows = await apiFetch('/api/devices?limit=1000')
        if (!active) return
        const catalog = Array.isArray(rows) ? rows : []
        setDevices(catalog)
        setSelectedDeviceId(catalog.length > 0 ? String(catalog[0].device_id) : '')
      } catch (requestError) {
        if (active) setError(requestError.message || 'Không tải được danh sách thiết bị')
      } finally {
        if (active) setDevicesLoading(false)
      }
    }
    loadDevices()
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!selectedDeviceId) {
      setSummary(EMPTY_SUMMARY)
      return undefined
    }
    void refreshSummary(selectedDeviceId)
    return undefined
  }, [refreshSummary, selectedDeviceId])

  useEffect(() => {
    let disposed = false
    let socket = null
    let reconnectTimer = null

    const connect = () => {
      if (disposed) return
      socket = openWebSocket('/ws/pings')
      socket.onmessage = (event) => {
        if (typeof event.data !== 'string') return
        try {
          const message = JSON.parse(event.data)
          const currentDeviceId = selectedDeviceIdRef.current
          if (
            message?.type === 'ping_stats_updated'
            && String(message.device_id) === currentDeviceId
          ) {
            void refreshSummary(currentDeviceId)
          }
        } catch {
          // Admin channel messages outside this contract are ignored.
        }
      }
      socket.onclose = () => {
        if (!disposed) reconnectTimer = window.setTimeout(connect, 1200)
      }
      socket.onerror = () => socket?.close()
    }

    connect()
    return () => {
      disposed = true
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [refreshSummary])

  const handleDelete = async () => {
    if (!selectedDeviceId || deleting) return
    const deviceId = selectedDeviceId
    setDeleting(true)
    setDeleteError('')
    try {
      await apiFetch(`/api/pings/${deviceId}`, { method: 'DELETE' })
      if (selectedDeviceIdRef.current === deviceId) setSummary(EMPTY_SUMMARY)
      await refreshSummary(deviceId)
      setDeleteOpen(false)
    } catch (requestError) {
      setDeleteError(requestError.message || 'Không thể xóa dữ liệu ping')
    } finally {
      setDeleting(false)
    }
  }

  const current = summary?.current_payload ?? null

  return (
    <section className="space-y-6" aria-labelledby="ping-page-title">
      <header className="flex items-center gap-3">
        <Activity aria-hidden="true" className="h-8 w-8 text-primary" />
        <div>
          <h1 id="ping-page-title" className="text-2xl font-bold text-foreground">Ping</h1>
          <p className="text-sm text-muted-foreground">Theo dõi application-level ping theo Device ID.</p>
        </div>
      </header>

      <div className="max-w-md space-y-2">
        <label htmlFor="ping-device-filter" className="block text-sm font-medium text-foreground">
          Lọc theo Device ID
        </label>
        {devicesLoading ? (
          <p className="text-sm text-muted-foreground">Đang tải danh sách thiết bị...</p>
        ) : (
          <select
            id="ping-device-filter"
            value={selectedDeviceId}
            onChange={(event) => setSelectedDeviceId(event.target.value)}
            disabled={devices.length === 0}
            className="min-h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
          >
            {devices.length === 0 && <option value="">Không có thiết bị</option>}
            {devices.map((device) => (
              <option key={device.device_id} value={String(device.device_id)}>
                {device.devicename || 'Thiết bị'} ({device.device_id})
              </option>
            ))}
          </select>
        )}
      </div>

      <AlertDialog
        open={deleteOpen}
        onOpenChange={(open) => {
          if (deleting) return
          setDeleteOpen(open)
          if (!open) setDeleteError('')
        }}
      >
        <AlertDialogTrigger asChild>
          <Button
            type="button"
            variant="destructive"
            disabled={!selectedDeviceId || devicesLoading || summaryLoading || deleting}
          >
            <Trash2 aria-hidden="true" />
            Xóa dữ liệu ping
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Xác nhận xóa dữ liệu ping</AlertDialogTitle>
            <AlertDialogDescription>
              Device ID: {selectedDeviceId}. Thao tác này xóa toàn bộ dữ liệu trong ping_payload và
              missing_ping_payload của thiết bị. Predicted order sẽ trở về 1 và không thể hoàn tác.
            </AlertDialogDescription>
          </AlertDialogHeader>
          {deleteError && (
            <p role="alert" className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              {deleteError}
            </p>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Hủy</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleting}
              className="bg-destructive text-white hover:bg-destructive/90"
              onClick={(event) => {
                event.preventDefault()
                void handleDelete()
              }}
            >
              {deleting ? 'Đang xóa...' : 'Xác nhận xóa'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {error && <p role="alert" className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
      {summaryLoading && <p role="status" className="text-sm text-muted-foreground">Đang tải thống kê ping...</p>}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <StatCard title="Total payload" icon={PackageCheck}>
          <p className="text-3xl font-bold text-foreground">{summary?.total_payload ?? 0}</p>
        </StatCard>
        <StatCard title="Current payload" icon={Clock3}>
          {current ? (
            <div className="space-y-1">
              <p className="text-2xl font-bold text-foreground">Order {current.order}</p>
              <p className="text-sm text-muted-foreground">Node uptime (ms): {current.timestamp}</p>
            </div>
          ) : (
            <div className="space-y-1">
              <p className="text-3xl font-bold text-foreground">—</p>
              <p className="text-sm text-muted-foreground">Chưa có payload ping</p>
            </div>
          )}
        </StatCard>
        <StatCard title="Total missing payload" icon={PackageX}>
          <p className="text-3xl font-bold text-foreground">{summary?.total_missing_payload ?? 0}</p>
        </StatCard>
      </div>
    </section>
  )
}
