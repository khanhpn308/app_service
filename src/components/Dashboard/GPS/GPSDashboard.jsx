import React, { useState, useMemo, useEffect } from 'react';
import MapViewer from './MapViewer';
import MapGroupManagerDialog from './MapGroupManagerDialog';
import { apiFetch } from '../../../lib/api';

const getColor = (id) => {
  const colors = ['#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899'];
  let hash = 0;
  const strId = String(id || '');
  for (let i = 0; i < strId.length; i++) {
    hash = strId.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
};

const GPSDashboard = ({ initialDevices = [] }) => {
  const [locations, setLocations] = useState([]);
  const [selectedLocation, setSelectedLocation] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [floorplanCache, setFloorplanCache] = useState({});
  const [floorplanError, setFloorplanError] = useState({});
  const [isPrefetching, setIsPrefetching] = useState(false);

  // Fetch danh sách location từ API (Quét thư mục SVG)
  useEffect(() => {
    const fetchLocations = async () => {
      try {
        const res = await apiFetch('/api/locations');
        if (import.meta.env.DEV) console.log('[GPSDashboard] Locations API Response:', res);
        if (res && res.data) {
          setLocations(res.data);
          // Mặc định chọn location đầu tiên nếu danh sách không rỗng
          if (res.data.length > 0) {
            setSelectedLocation(prev => prev || res.data[0]);
          } else if (res.error) {
            console.error('[GPSDashboard] API Error:', res.error, 'Path:', res.scanned_path);
          }
        }
      } catch (err) {
        console.error('Failed to fetch locations:', err);
      }
    };
    fetchLocations();
  }, []);

  // Prefetch tất cả ảnh mặt bằng (webp) ngay khi vào dashboard để cache trong trình duyệt (blob URL)
  useEffect(() => {
    if (!locations || locations.length === 0) return;

    let mounted = true;
    const controller = new AbortController();

    // Cleanup cache cũ
    setFloorplanCache((prev) => {
      Object.values(prev || {}).forEach((url) => {
        try {
          if (url) URL.revokeObjectURL(url);
        } catch {
          // ignore
        }
      });
      return {};
    });
    setFloorplanError({});
    setIsPrefetching(true);

    const token = localStorage.getItem('iot_token');
    const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};

    (async () => {
      for (const loc of locations) {
        const name = String(loc || '').trim();
        if (!name) continue;

        try {
          const url = `/api/floorplans/${encodeURIComponent(name)}.webp`;
          const res = await fetch(url, {
            method: 'GET',
            headers: authHeaders,
            signal: controller.signal,
          });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const blob = await res.blob();
          if (!mounted) return;

          const objectUrl = URL.createObjectURL(blob);
          setFloorplanCache((prev) => ({ ...prev, [name]: objectUrl }));
        } catch {
          if (!mounted) return;
          setFloorplanError((prev) => ({ ...prev, [name]: true }));
        }
      }
    })()
      .finally(() => {
        if (!mounted) return;
        setIsPrefetching(false);
      });

    return () => {
      mounted = false;
      controller.abort();
      setFloorplanCache((prev) => {
        Object.values(prev || {}).forEach((url) => {
          try {
            if (url) URL.revokeObjectURL(url);
          } catch {
            // ignore
          }
        });
        return {};
      });
    };
  }, [JSON.stringify(locations)]);


  // Lọc thiết bị dựa trên location đang chọn và chuỗi tìm kiếm
  const filteredDevices = useMemo(() => {
    const selectedLoc = String(selectedLocation || '').trim().toLowerCase();
    return (initialDevices || []).filter(d => {
      // So khớp location không phân biệt hoa/thường: payload gửi "FLOOR_1"
      // nhưng tên file floorplan có thể là "Floor_1" -> vẫn phải khớp.
      const locationMatch = String(d.location || '').trim().toLowerCase() === selectedLoc;
      const idStr = String(d.device_id || '').toLowerCase();
      const searchMatch = idStr.includes(searchQuery.toLowerCase());
      return locationMatch && searchMatch;
    });
  }, [initialDevices, selectedLocation, searchQuery]);

  return (
    <div className="flex h-full flex-col bg-white">
      {/* Thanh công cụ lọc */}
      <div className="flex flex-wrap items-center gap-4 p-4 border-b border-gray-100">
        <div className="flex flex-col">
          <label className="text-[10px] font-bold text-gray-400 uppercase mb-1">Khu vực (Map)</label>
          <select
            value={selectedLocation}
            onChange={(e) => setSelectedLocation(e.target.value)}
            className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 p-2 min-w-[180px]"
          >
            {locations.map(loc => (
              <option key={loc} value={loc}>
                {loc.toUpperCase().replace('-', ' ')}
              </option>
            ))}
            {locations.length === 0 && <option value="">Không có bản đồ</option>}
          </select>
        </div>

        <div className="flex min-w-[14rem] flex-1 flex-col max-w-md">
          <label className="text-[10px] font-bold text-gray-400 uppercase mb-1">Tìm thiết bị</label>
          <div className="relative">
            <input
              type="text"
              placeholder="Nhập mã thiết bị..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg p-2 pl-10 focus:ring-blue-500 focus:border-blue-500"
            />
            <span className="absolute left-3 top-2 text-gray-400">🔍</span>
          </div>
        </div>

        <div className="ml-auto self-end">
          <MapGroupManagerDialog />
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden min-w-0">
        {/* Khu vực hiển thị bản đồ chính */}
        <div className="flex-1 p-6 overflow-hidden bg-gray-50/50 min-w-0">
          <div className="max-w-5xl mx-auto min-w-0">
            <header className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-xl font-bold text-gray-800">Bản đồ GPS Realtime</h2>
                <p className="text-sm text-gray-500 italic">Vị trí hiện tại tại {selectedLocation || '...'}</p>
              </div>
              <div className="flex items-center gap-2 bg-green-50 px-3 py-1 rounded-full border border-green-100">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                <span className="text-[10px] font-bold text-green-700 uppercase">Live Tracking</span>
              </div>
            </header>

            <MapViewer
              locationName={selectedLocation}
              floorplanUrl={floorplanCache[selectedLocation] || ''}
              isLoading={isPrefetching && !!selectedLocation && !floorplanCache[selectedLocation] && !floorplanError[selectedLocation]}
              hasError={!!selectedLocation && !!floorplanError[selectedLocation]}
              devices={filteredDevices}
              getColor={getColor}
            />
          </div>
        </div>

        {/* Sidebar danh sách thiết bị bên phải */}
        <aside className="w-80 border-l border-gray-100 bg-white flex flex-col shadow-xl">
          <div className="p-4 border-b border-gray-100">
            <h3 className="font-bold text-gray-700 flex items-center justify-between">
              Thiết bị hiển thị
              <span className="bg-blue-100 text-blue-700 text-[10px] px-2 py-0.5 rounded-full">
                {filteredDevices.length}
              </span>
            </h3>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {filteredDevices.map((dev) => (
              <div
                key={dev.device_id}
                className="group bg-gray-50 p-3 rounded-xl border border-transparent hover:border-blue-200 hover:bg-white hover:shadow-md transition-all duration-200"
              >
                <div className="flex items-center gap-3 mb-2">
                  <div
                    className="w-3 h-3 rounded-full shadow-sm"
                    style={{ backgroundColor: getColor(dev.device_id) }}
                  />
                  <span className="text-sm font-bold text-gray-800 truncate flex-1">{dev.device_id}</span>
                  <span className="text-[10px] font-mono text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">
                    {dev.ts_iso ? dev.ts_iso.split('T')[1].split('.')[0] : 'No data'}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-[10px] text-gray-500 bg-white/50 p-2 rounded-lg">
                  <div className="flex flex-col">
                    <span className="text-gray-400 uppercase font-medium">Tọa độ X</span>
                    <span className="font-bold text-gray-700">{dev.x !== null ? `${dev.x}%` : 'N/A'}</span>
                  </div>
                  <div className="flex flex-col border-l border-gray-100 pl-2">
                    <span className="text-gray-400 uppercase font-medium">Tọa độ Y</span>
                    <span className="font-bold text-gray-700">{dev.y !== null ? `${dev.y}%` : 'N/A'}</span>
                  </div>
                </div>
              </div>
            ))}
            {filteredDevices.length === 0 && (
              <div className="flex flex-col items-center justify-center py-20 text-gray-400">
                <span className="text-4xl mb-2">📍</span>
                <p className="text-sm">Không có thiết bị trong khu vực này</p>
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
};

export default GPSDashboard;
