import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { List, PanelLeft, Plus, Trash2 } from 'lucide-react'

import { useAuth } from '@/contexts/AuthContext'
import { createAnchor, deleteAnchor, listLocationAnchors, updateAnchor } from '@/lib/anchorsApi'
import { listMapGroups } from '@/lib/mapGroupsApi'
import { deleteMap, fetchMapImage, listGroupMaps } from '@/lib/mapsApi'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'

import MapGroupManagerDialog from './MapGroupManagerDialog'
import AnchorEditorDialog from './AnchorEditorDialog'
import AnchorManagerDialog from './AnchorManagerDialog'
import AnchorSyncStatus from './AnchorSyncStatus'
import MapViewer from './MapViewer'
import UploadMapDialog from './UploadMapDialog'

const getColor = (id) => {
  const colors = ['#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899']
  let hash = 0
  const stringId = String(id || '')
  for (let index = 0; index < stringId.length; index += 1) {
    hash = stringId.charCodeAt(index) + ((hash << 5) - hash)
  }
  return colors[Math.abs(hash) % colors.length]
}

const getDeviceName = (device) => {
  const deviceId = String(device?.device_id ?? '')
  return String(device?.devicename ?? '').trim() || deviceId
}

const getDeviceIdentity = (device) => {
  const deviceId = String(device?.device_id ?? '')
  const deviceName = getDeviceName(device)
  return deviceName === deviceId ? deviceId : `${deviceName}(${deviceId})`
}

const formatClockTime = (date) =>
  [date.getHours(), date.getMinutes(), date.getSeconds()]
    .map((value) => String(value).padStart(2, '0'))
    .join(':')

function DashboardClock() {
  const [currentTime, setCurrentTime] = useState(() => new Date())

  useEffect(() => {
    const intervalId = window.setInterval(() => setCurrentTime(new Date()), 1000)
    return () => window.clearInterval(intervalId)
  }, [])

  return (
    <time
      aria-label="Thời gian hiện tại"
      dateTime={currentTime.toISOString()}
      className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1 font-mono text-sm font-bold tabular-nums text-blue-700"
    >
      {formatClockTime(currentTime)}
    </time>
  )
}

function DevicePanelContent({ devices }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b border-slate-200 p-4">
        <h3 className="flex items-center justify-between font-bold text-gray-700">
          Thiết bị hiển thị
          <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] text-blue-700">
            {devices.length}
          </span>
        </h3>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-3">
        {devices.map((device) => (
          <div
            key={device.device_id}
            className="group rounded-xl border border-transparent bg-gray-50 p-3 transition-all duration-200 hover:border-blue-200 hover:bg-white hover:shadow-md"
          >
            <div className="flex items-center gap-3">
              <div
                className="h-3 w-3 rounded-full shadow-sm"
                style={{ backgroundColor: getColor(device.device_id) }}
              />
              <span
                title={getDeviceIdentity(device)}
                className="flex-1 truncate text-sm font-bold text-gray-800"
              >
                {getDeviceIdentity(device)}
              </span>
            </div>
          </div>
        ))}
        {devices.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-gray-400">
            <span className="mb-2 text-4xl">📍</span>
            <p className="text-sm">Không có thiết bị trong khu vực này</p>
          </div>
        )}
      </div>
    </div>
  )
}

const GPSDashboard = ({ initialDevices = [] }) => {
  const { user, refreshUser } = useAuth()
  const [groups, setGroups] = useState([])
  const [selectedGroupId, setSelectedGroupId] = useState('')
  const [maps, setMaps] = useState([])
  const [selectedMapId, setSelectedMapId] = useState('')
  const [floorplanUrl, setFloorplanUrl] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [loadingMap, setLoadingMap] = useState(false)
  const [error, setError] = useState('')
  const [anchors, setAnchors] = useState([])
  const [anchorEditor, setAnchorEditor] = useState(null)
  const [anchorPermissionRevoked, setAnchorPermissionRevoked] = useState(false)
  const [anchorNavigation, setAnchorNavigation] = useState(null)
  const [floorplanReadyId, setFloorplanReadyId] = useState(null)
  const [anchorsReadyId, setAnchorsReadyId] = useState(null)
  const preferredMapId = useRef(null)
  const anchorNavigationRef = useRef(null)
  const selectedMapIdRef = useRef('')

  const selectedGroup = groups.find(
    (group) => group.group_id === Number(selectedGroupId),
  )
  const selectedMap = maps.find(
    (map) => map.location_id === Number(selectedMapId),
  )
  const canConfigureAnchors = !anchorPermissionRevoked && (
    user?.role === 'admin' || (
      selectedGroup?.access_role === 'owner' && user?.can_config_anchor === 'yes'
    )
  )
  const canAccessAnchorManager = !anchorPermissionRevoked && (
    user?.role === 'admin' || user?.can_config_anchor === 'yes'
  )

  const cancelAnchorNavigation = useCallback((message = '') => {
    anchorNavigationRef.current = null
    setAnchorNavigation(null)
    if (message) setError(message)
  }, [])

  const loadGroups = useCallback(async () => {
    try {
      const nextGroups = await listMapGroups()
      setGroups(nextGroups)
      setSelectedGroupId((current) =>
        nextGroups.some((group) => group.group_id === Number(current))
          ? current
          : String(nextGroups[0]?.group_id ?? ''),
      )
    } catch (requestError) {
      setError(requestError.message || 'Không thể tải nhóm bản đồ.')
    }
  }, [])

  const loadMaps = useCallback(async (groupId, preferredId = null) => {
    if (!groupId) {
      setMaps([])
      setSelectedMapId('')
      return
    }
    setLoadingMap(true)
    setError('')
    try {
      const nextMaps = await listGroupMaps(Number(groupId))
      setMaps(nextMaps)
      const wanted = preferredId ?? preferredMapId.current ?? Number(selectedMapIdRef.current)
      preferredMapId.current = null
      const match = nextMaps.find((map) => map.location_id === Number(wanted))
      const navigation = anchorNavigationRef.current
      if (
        navigation &&
        navigation.groupId === Number(groupId) &&
        navigation.locationId === Number(wanted) &&
        !match
      ) {
        cancelAnchorNavigation('Anchor hoặc map không còn quyền truy cập.')
      }
      const nextMapId = String(match?.location_id ?? nextMaps[0]?.location_id ?? '')
      selectedMapIdRef.current = nextMapId
      setSelectedMapId(nextMapId)
    } catch (requestError) {
      setMaps([])
      setSelectedMapId('')
      setError(requestError.message || 'Không thể tải danh sách bản đồ.')
    } finally {
      setLoadingMap(false)
    }
  }, [cancelAnchorNavigation])

  useEffect(() => {
    loadGroups()
  }, [loadGroups])

  useEffect(() => {
    setMaps([])
    selectedMapIdRef.current = ''
    setSelectedMapId('')
    loadMaps(selectedGroupId)
  }, [loadMaps, selectedGroupId])

  useEffect(() => {
    let active = true
    let objectUrl = ''
    setFloorplanUrl('')
    setFloorplanReadyId(null)
    if (!selectedMapId) return () => {}

    setLoadingMap(true)
    fetchMapImage(Number(selectedMapId))
      .then((blob) => {
        if (!active) return
        objectUrl = URL.createObjectURL(blob)
        setFloorplanUrl(objectUrl)
        setFloorplanReadyId(Number(selectedMapId))
      })
      .catch((requestError) => {
        if (active) {
          const navigation = anchorNavigationRef.current
          if (navigation?.locationId === Number(selectedMapId)) {
            cancelAnchorNavigation('Anchor hoặc map không còn quyền truy cập.')
          } else {
            setError(requestError.message || 'Không thể tải ảnh bản đồ.')
          }
        }
      })
      .finally(() => {
        if (active) setLoadingMap(false)
      })

    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [cancelAnchorNavigation, selectedMapId])

  useEffect(() => {
    const controller = new AbortController()
    setAnchors([])
    setAnchorsReadyId(null)
    setAnchorEditor(null)
    if (!selectedMapId) return () => controller.abort()

    listLocationAnchors(Number(selectedMapId), { signal: controller.signal })
      .then((nextAnchors) => {
        setAnchors(nextAnchors)
        setAnchorsReadyId(Number(selectedMapId))
      })
      .catch((requestError) => {
        if (requestError.name !== 'AbortError') {
          const navigation = anchorNavigationRef.current
          if (navigation?.locationId === Number(selectedMapId)) {
            cancelAnchorNavigation('Anchor hoặc map không còn quyền truy cập.')
          } else {
            setError(requestError.message || 'Không thể tải danh sách Anchor.')
          }
        }
      })
    return () => controller.abort()
  }, [cancelAnchorNavigation, selectedMapId])

  useEffect(() => {
    if (!anchorNavigation) return
    const targetGroup = groups.find((group) => group.group_id === anchorNavigation.groupId)
    const allowed = user?.role === 'admin' || (
      user?.can_config_anchor === 'yes' && targetGroup?.access_role === 'owner'
    )
    if (selectedGroupId === String(anchorNavigation.groupId) && !allowed) {
      cancelAnchorNavigation('Quyền cấu hình Anchor đã thay đổi.')
      return
    }
    if (
      selectedMapId !== String(anchorNavigation.locationId) ||
      floorplanReadyId !== anchorNavigation.locationId ||
      anchorsReadyId !== anchorNavigation.locationId
    ) return
    const freshAnchor = anchors.find((anchor) => anchor.anchor_id === anchorNavigation.anchorId)
    if (!freshAnchor) {
      cancelAnchorNavigation('Anchor không còn tồn tại hoặc không còn quyền truy cập.')
      return
    }
    cancelAnchorNavigation()
    setAnchorEditor({ mode: 'edit', anchor: freshAnchor })
  }, [anchorNavigation, anchors, anchorsReadyId, cancelAnchorNavigation, floorplanReadyId, groups, selectedGroupId, selectedMapId, user?.can_config_anchor, user?.role])

  useEffect(() => {
    setAnchorPermissionRevoked(false)
  }, [user?.user_id, user?.can_config_anchor, selectedGroupId])

  const revokeAnchorPermission = useCallback(async () => {
    setAnchorPermissionRevoked(true)
    setAnchorEditor(null)
    await refreshUser()
  }, [refreshUser])

  const handleAnchorFailure = useCallback(async (requestError) => {
    if (requestError?.status === 403) await revokeAnchorPermission()
    throw requestError
  }, [revokeAnchorPermission])

  const saveAnchor = async (payload) => {
    try {
      if (anchorEditor.mode === 'create') {
        const result = await createAnchor(Number(selectedMapId), payload)
        setAnchors((current) => [...current, result.data])
      } else {
        const result = await updateAnchor(anchorEditor.anchor.anchor_id, payload)
        setAnchors((current) => current.map((item) => (
          item.anchor_id === result.data.anchor_id ? result.data : item
        )))
      }
      setAnchorEditor(null)
    } catch (requestError) {
      await handleAnchorFailure(requestError)
    }
  }

  const removeAnchor = async () => {
    try {
      await deleteAnchor(anchorEditor.anchor.anchor_id)
      setAnchors((current) => current.filter((item) => item.anchor_id !== anchorEditor.anchor.anchor_id))
      setAnchorEditor(null)
    } catch (requestError) {
      await handleAnchorFailure(requestError)
    }
  }

  const displayAnchors = useMemo(() => {
    if (!anchorEditor) return anchors
    if (anchorEditor.mode === 'create') return [...anchors, anchorEditor.anchor]
    return anchors.map((item) => item.anchor_id === anchorEditor.anchor.anchor_id ? anchorEditor.anchor : item)
  }, [anchorEditor, anchors])

  const handleUploaded = async (uploaded) => {
    if (uploaded.group_id === Number(selectedGroupId)) {
      await loadMaps(selectedGroupId, uploaded.location_id)
    } else {
      preferredMapId.current = uploaded.location_id
      setSelectedGroupId(String(uploaded.group_id))
    }
  }

  const handleAnchorCatalogSelect = (anchor) => {
    const targetGroup = groups.find((group) => group.group_id === anchor.group_id)
    const allowed = user?.role === 'admin' || (
      user?.can_config_anchor === 'yes' && targetGroup?.access_role === 'owner'
    )
    if (!targetGroup || !allowed) {
      setError('Anchor hoặc group không còn quyền truy cập.')
      return
    }
    const navigation = {
      anchorId: anchor.anchor_id,
      groupId: anchor.group_id,
      locationId: anchor.location_id,
    }
    anchorNavigationRef.current = navigation
    setAnchorNavigation(navigation)
    setAnchorEditor(null)
    preferredMapId.current = anchor.location_id
    if (Number(selectedGroupId) === anchor.group_id) {
      const targetMap = maps.find((map) => map.location_id === anchor.location_id)
      if (targetMap) {
        preferredMapId.current = null
        selectedMapIdRef.current = String(anchor.location_id)
        setSelectedMapId(String(anchor.location_id))
      } else {
        loadMaps(selectedGroupId, anchor.location_id)
      }
    } else {
      setSelectedGroupId(String(anchor.group_id))
    }
  }

  const handleGroupSelection = (value) => {
    if (anchorNavigationRef.current) {
      cancelAnchorNavigation('Đã hủy mở Anchor vì nhóm bản đồ thay đổi.')
    }
    setSelectedGroupId(value)
  }

  const handleMapSelection = (value) => {
    if (anchorNavigationRef.current) {
      cancelAnchorNavigation('Đã hủy mở Anchor vì map thay đổi.')
    }
    setSelectedMapId(value)
    selectedMapIdRef.current = value
  }

  const handleDelete = async () => {
    if (!selectedMap || !selectedGroup?.can_manage) return
    if (!window.confirm(`Xóa bản đồ “${selectedMap.location}”?`)) return
    try {
      await deleteMap(selectedMap.location_id)
      await loadMaps(selectedGroupId)
    } catch (requestError) {
      setError(requestError.message || 'Không thể xóa bản đồ.')
    }
  }

  const filteredDevices = useMemo(() => {
    const selectedLocation = String(selectedMap?.location || '').trim().toLowerCase()
    const normalizedSearch = searchQuery.trim().toLowerCase()
    return (initialDevices || []).filter((device) => {
      const locationMatches =
        String(device.location || '').trim().toLowerCase() === selectedLocation
      const searchMatches =
        getDeviceName(device).toLowerCase().includes(normalizedSearch) ||
        String(device.device_id ?? '').toLowerCase().includes(normalizedSearch)
      return locationMatches && searchMatches
    })
  }, [initialDevices, searchQuery, selectedMap])

  const renderSystemActions = () => (
    <div
      role="toolbar"
      aria-label="Thao tác bản đồ"
      aria-orientation="vertical"
      className="flex w-full flex-col gap-2 [&>button]:min-h-11 [&>button]:w-full [&>button]:justify-start [&>div>button]:min-h-11 [&>div>button]:w-full [&>div>button]:justify-start"
    >
      <UploadMapDialog
        groups={groups}
        defaultGroupId={selectedGroupId}
        onUploaded={handleUploaded}
      />
      {canConfigureAnchors && selectedMap && (
        <Button
          type="button"
          variant="outline"
          className="w-full justify-start gap-2"
          onClick={() => setAnchorEditor({
            mode: 'create',
            anchor: { mac_address: '', name: '', x: 50, y: 50, z: 0 },
          })}
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          Thêm Anchor
        </Button>
      )}
      {canAccessAnchorManager && (
        <AnchorManagerDialog groups={groups} onSelect={handleAnchorCatalogSelect} />
      )}
      <AnchorSyncStatus
        locationId={selectedMap?.location_id}
        enabled={canConfigureAnchors}
        onPermissionRevoked={revokeAnchorPermission}
      />
      {selectedGroup?.can_manage && selectedMap && (
        <Button type="button" variant="destructive" className="w-full justify-start gap-2" onClick={handleDelete}>
          <Trash2 className="h-4 w-4" aria-hidden="true" />
          Xóa bản đồ
        </Button>
      )}
      <MapGroupManagerDialog onGroupsChanged={loadGroups} />
    </div>
  )

  return (
    <div className="relative grid h-full min-h-0 grid-cols-1 overflow-hidden bg-slate-100 lg:grid-cols-[15rem_minmax(0,1fr)_18.75rem]">
      <aside
        aria-label="Hệ thống"
        className="hidden min-h-0 flex-col border-r border-slate-800 bg-slate-950 text-slate-100 shadow-[6px_0_18px_-12px_rgba(15,23,42,0.8)] lg:flex"
      >
        <div className="border-b border-slate-800 px-4 py-5">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Hệ thống</p>
          <h2 className="mt-1 text-base font-semibold text-white">Cấu hình bản đồ</h2>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          {renderSystemActions()}
        </div>
      </aside>

      <section aria-label="Không gian bản đồ" className="flex min-h-0 min-w-0 flex-col bg-slate-100">
        <div
          role="toolbar"
          aria-label="Bộ lọc bản đồ"
          className="grid shrink-0 gap-3 border-b border-slate-200 bg-white p-3 shadow-[0_5px_16px_-14px_rgba(15,23,42,0.9)] sm:grid-cols-2 xl:grid-cols-[minmax(10rem,13rem)_minmax(10rem,13rem)_minmax(14rem,1fr)]"
        >
          <div className="flex min-w-0 flex-col">
            <label htmlFor="gps-map-group" className="mb-1 text-[10px] font-bold uppercase tracking-wide text-slate-500">
              Nhóm bản đồ
            </label>
            <select
              id="gps-map-group"
              value={selectedGroupId}
              onChange={(event) => handleGroupSelection(event.target.value)}
              className="min-h-11 w-full min-w-0 rounded-lg border border-slate-300 bg-slate-50 px-3 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
            >
              {groups.map((group) => (
                <option key={group.group_id} value={group.group_id}>{group.name}</option>
              ))}
              {groups.length === 0 && <option value="">Không có nhóm</option>}
            </select>
          </div>

          <div className="flex min-w-0 flex-col">
            <label htmlFor="gps-map-location" className="mb-1 text-[10px] font-bold uppercase tracking-wide text-slate-500">
              Khu vực (Map)
            </label>
            <select
              id="gps-map-location"
              value={selectedMapId}
              onChange={(event) => handleMapSelection(event.target.value)}
              className="min-h-11 w-full min-w-0 rounded-lg border border-slate-300 bg-slate-50 px-3 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
            >
              {maps.map((map) => (
                <option key={map.location_id} value={map.location_id}>{map.location}</option>
              ))}
              {maps.length === 0 && <option value="">Không có bản đồ</option>}
            </select>
          </div>

          <div className="flex min-w-0 flex-col sm:col-span-2 xl:col-span-1">
            <label htmlFor="gps-device-search" className="mb-1 text-[10px] font-bold uppercase tracking-wide text-slate-500">
              Tìm thiết bị
            </label>
            <input
              id="gps-device-search"
              type="search"
              placeholder="Nhập tên hoặc mã thiết bị..."
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              className="min-h-11 w-full rounded-lg border border-slate-300 bg-slate-50 px-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
            />
          </div>

          <div className="flex gap-2 sm:col-span-2 lg:hidden">
            <Sheet>
              <SheetTrigger asChild>
                <Button type="button" variant="outline" className="min-h-11 flex-1 gap-2">
                  <PanelLeft className="h-4 w-4" aria-hidden="true" />
                  Hệ thống
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="gap-0 border-slate-800 bg-slate-950 p-0 text-slate-100">
                <SheetHeader className="border-b border-slate-800 text-left">
                  <SheetTitle className="text-white">Hệ thống</SheetTitle>
                  <SheetDescription className="text-slate-400">Cấu hình bản đồ và Anchor</SheetDescription>
                </SheetHeader>
                <div className="min-h-0 flex-1 overflow-y-auto p-3">{renderSystemActions()}</div>
              </SheetContent>
            </Sheet>
            <Sheet>
              <SheetTrigger asChild>
                <Button type="button" variant="outline" className="min-h-11 flex-1 gap-2">
                  <List className="h-4 w-4" aria-hidden="true" />
                  Thiết bị ({filteredDevices.length})
                </Button>
              </SheetTrigger>
              <SheetContent side="right" className="gap-0 p-0">
                <SheetHeader className="sr-only">
                  <SheetTitle>Thiết bị hiển thị</SheetTitle>
                  <SheetDescription>Danh sách thiết bị trong khu vực đang chọn</SheetDescription>
                </SheetHeader>
                <DevicePanelContent devices={filteredDevices} />
              </SheetContent>
            </Sheet>
          </div>
        </div>

        {error && (
          <div role="alert" className="border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>
        )}

        <div
          data-testid="map-surface"
          className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-white"
        >
          <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 shadow-[0_5px_16px_-14px_rgba(15,23,42,0.9)]">
            <div className="min-w-0">
              <h2 className="truncate text-lg font-bold text-slate-800">Bản đồ Realtime</h2>
              <p className="truncate text-sm text-slate-500">Vị trí hiện tại tại {selectedMap?.location || '...'}</p>
            </div>
            <DashboardClock />
          </header>

          <MapViewer
            locationName={selectedMap?.location || ''}
            floorplanUrl={floorplanUrl}
            isLoading={loadingMap}
            hasError={!!selectedMap && !!error && !floorplanUrl}
            devices={filteredDevices}
            anchors={displayAnchors}
            canConfigureAnchors={canConfigureAnchors}
            onAnchorClick={(anchor) => setAnchorEditor({ mode: anchor.anchor_id ? 'edit' : 'create', anchor })}
            onAnchorMove={(anchor, x, y) => setAnchorEditor((current) => ({
              mode: anchor.anchor_id ? 'edit' : 'create',
              anchor: { ...(current?.anchor?.anchor_id === anchor.anchor_id ? current.anchor : anchor), x, y },
            }))}
            getColor={getColor}
            getDeviceName={getDeviceName}
          />
        </div>
      </section>

      <aside
        aria-label="Thiết bị hiển thị"
        className="hidden min-h-0 flex-col border-l border-slate-200 bg-white shadow-[-6px_0_18px_-14px_rgba(15,23,42,0.7)] lg:flex"
      >
        <DevicePanelContent devices={filteredDevices} />
      </aside>
      {canConfigureAnchors && anchorEditor && (
        <AnchorEditorDialog
          mode={anchorEditor.mode}
          anchor={anchorEditor.anchor}
          onChange={(anchor) => setAnchorEditor((current) => ({ ...current, anchor }))}
          onSave={saveAnchor}
          onDelete={anchorEditor.mode === 'edit' ? removeAnchor : undefined}
          onClose={() => setAnchorEditor(null)}
        />
      )}
    </div>
  )
}

export default GPSDashboard
