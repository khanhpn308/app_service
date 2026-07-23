import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Trash2 } from 'lucide-react'

import { listMapGroups } from '@/lib/mapGroupsApi'
import { deleteMap, fetchMapImage, listGroupMaps } from '@/lib/mapsApi'
import { Button } from '@/components/ui/button'

import MapGroupManagerDialog from './MapGroupManagerDialog'
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

function DeviceList({ devices }) {
  return (
    <aside className="flex w-80 flex-col border-l border-gray-100 bg-white shadow-xl">
      <div className="border-b border-gray-100 p-4">
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
            <div className="mb-2 flex items-center gap-3">
              <div
                className="h-3 w-3 rounded-full shadow-sm"
                style={{ backgroundColor: getColor(device.device_id) }}
              />
              <span className="flex-1 truncate text-sm font-bold text-gray-800">
                {device.device_id}
              </span>
              <span className="rounded bg-blue-50 px-1.5 py-0.5 font-mono text-[10px] text-blue-600">
                {device.ts_iso ? device.ts_iso.split('T')[1].split('.')[0] : 'No data'}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 rounded-lg bg-white/50 p-2 text-[10px] text-gray-500">
              <div className="flex flex-col">
                <span className="font-medium uppercase text-gray-400">Tọa độ X</span>
                <span className="font-bold text-gray-700">
                  {device.x !== null ? `${device.x}%` : 'N/A'}
                </span>
              </div>
              <div className="flex flex-col border-l border-gray-100 pl-2">
                <span className="font-medium uppercase text-gray-400">Tọa độ Y</span>
                <span className="font-bold text-gray-700">
                  {device.y !== null ? `${device.y}%` : 'N/A'}
                </span>
              </div>
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
    </aside>
  )
}

const GPSDashboard = ({ initialDevices = [] }) => {
  const [groups, setGroups] = useState([])
  const [selectedGroupId, setSelectedGroupId] = useState('')
  const [maps, setMaps] = useState([])
  const [selectedMapId, setSelectedMapId] = useState('')
  const [floorplanUrl, setFloorplanUrl] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [loadingMap, setLoadingMap] = useState(false)
  const [error, setError] = useState('')
  const preferredMapId = useRef(null)

  const selectedGroup = groups.find(
    (group) => group.group_id === Number(selectedGroupId),
  )
  const selectedMap = maps.find(
    (map) => map.location_id === Number(selectedMapId),
  )

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
      setSelectedMapId((current) => {
        const wanted = preferredId ?? preferredMapId.current ?? Number(current)
        preferredMapId.current = null
        const match = nextMaps.find((map) => map.location_id === Number(wanted))
        return String(match?.location_id ?? nextMaps[0]?.location_id ?? '')
      })
    } catch (requestError) {
      setMaps([])
      setSelectedMapId('')
      setError(requestError.message || 'Không thể tải danh sách bản đồ.')
    } finally {
      setLoadingMap(false)
    }
  }, [])

  useEffect(() => {
    loadGroups()
  }, [loadGroups])

  useEffect(() => {
    setMaps([])
    setSelectedMapId('')
    loadMaps(selectedGroupId)
  }, [loadMaps, selectedGroupId])

  useEffect(() => {
    let active = true
    let objectUrl = ''
    setFloorplanUrl('')
    if (!selectedMapId) return () => {}

    setLoadingMap(true)
    fetchMapImage(Number(selectedMapId))
      .then((blob) => {
        if (!active) return
        objectUrl = URL.createObjectURL(blob)
        setFloorplanUrl(objectUrl)
      })
      .catch((requestError) => {
        if (active) setError(requestError.message || 'Không thể tải ảnh bản đồ.')
      })
      .finally(() => {
        if (active) setLoadingMap(false)
      })

    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [selectedMapId])

  const handleUploaded = async (uploaded) => {
    if (uploaded.group_id === Number(selectedGroupId)) {
      await loadMaps(selectedGroupId, uploaded.location_id)
    } else {
      preferredMapId.current = uploaded.location_id
      setSelectedGroupId(String(uploaded.group_id))
    }
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
    return (initialDevices || []).filter((device) => {
      const locationMatches =
        String(device.location || '').trim().toLowerCase() === selectedLocation
      const searchMatches = String(device.device_id || '')
        .toLowerCase()
        .includes(searchQuery.toLowerCase())
      return locationMatches && searchMatches
    })
  }, [initialDevices, searchQuery, selectedMap])

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex flex-wrap items-end gap-4 border-b border-gray-100 p-4">
        <div className="flex flex-col">
          <label htmlFor="gps-map-group" className="mb-1 text-[10px] font-bold uppercase text-gray-400">
            Nhóm bản đồ
          </label>
          <select
            id="gps-map-group"
            value={selectedGroupId}
            onChange={(event) => setSelectedGroupId(event.target.value)}
            className="min-w-[180px] rounded-lg border border-gray-300 bg-gray-50 p-2 text-sm text-gray-900"
          >
            {groups.map((group) => (
              <option key={group.group_id} value={group.group_id}>
                {group.name}
              </option>
            ))}
            {groups.length === 0 && <option value="">Không có nhóm</option>}
          </select>
        </div>

        <div className="flex flex-col">
          <label htmlFor="gps-map-location" className="mb-1 text-[10px] font-bold uppercase text-gray-400">
            Khu vực (Map)
          </label>
          <select
            id="gps-map-location"
            value={selectedMapId}
            onChange={(event) => setSelectedMapId(event.target.value)}
            className="min-w-[180px] rounded-lg border border-gray-300 bg-gray-50 p-2 text-sm text-gray-900"
          >
            {maps.map((map) => (
              <option key={map.location_id} value={map.location_id}>
                {map.location}
              </option>
            ))}
            {maps.length === 0 && <option value="">Không có bản đồ</option>}
          </select>
        </div>

        <div className="flex min-w-[14rem] max-w-md flex-1 flex-col">
          <label htmlFor="gps-device-search" className="mb-1 text-[10px] font-bold uppercase text-gray-400">
            Tìm thiết bị
          </label>
          <input
            id="gps-device-search"
            type="search"
            placeholder="Nhập mã thiết bị..."
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            className="w-full rounded-lg border border-gray-300 bg-gray-50 p-2 text-sm text-gray-900"
          />
        </div>

        <UploadMapDialog
          groups={groups}
          defaultGroupId={selectedGroupId}
          onUploaded={handleUploaded}
        />
        {selectedGroup?.can_manage && selectedMap && (
          <Button type="button" variant="destructive" className="gap-2" onClick={handleDelete}>
            <Trash2 className="h-4 w-4" aria-hidden="true" />
            Xóa bản đồ
          </Button>
        )}
        <MapGroupManagerDialog />
      </div>

      {error && (
        <div role="alert" className="border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="flex min-w-0 flex-1 overflow-hidden">
        <div className="min-w-0 flex-1 overflow-hidden bg-gray-50/50 p-6">
          <div className="mx-auto max-w-5xl min-w-0">
            <header className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-gray-800">Bản đồ GPS Realtime</h2>
                <p className="text-sm italic text-gray-500">
                  Vị trí hiện tại tại {selectedMap?.location || '...'}
                </p>
              </div>
              <div className="flex items-center gap-2 rounded-full border border-green-100 bg-green-50 px-3 py-1">
                <div className="h-2 w-2 animate-pulse rounded-full bg-green-500" />
                <span className="text-[10px] font-bold uppercase text-green-700">Live Tracking</span>
              </div>
            </header>

            <MapViewer
              locationName={selectedMap?.location || ''}
              floorplanUrl={floorplanUrl}
              isLoading={loadingMap}
              hasError={!!selectedMap && !!error && !floorplanUrl}
              devices={filteredDevices}
              getColor={getColor}
            />
          </div>
        </div>

        <DeviceList devices={filteredDevices} />
      </div>
    </div>
  )
}

export default GPSDashboard
