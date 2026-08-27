import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Cpu, MapPin, Clock, ExternalLink, Plus, Search, Trash2 } from 'lucide-react';
import { apiFetch } from '../lib/api';
import { openWebSocket } from '../lib/wsUrl';
import { toUiStatus } from '../lib/deviceStatus';
import AddDeviceModal from '../components/AddDeviceModal';
import { Skeleton } from '../components/ui/skeleton';
import { Button } from '../components/ui/button';
import { PageHeader } from '../components/common/PageHeader';
import { StatusBadge } from '../components/common/StatusBadge';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogCancel,
  AlertDialogAction,
} from '../components/ui/alert-dialog';

const DeviceCardSkeleton = () => (
  <div className="bg-card rounded-xl border border-border overflow-hidden p-6 space-y-4">
    <div className="flex items-center gap-3">
      <Skeleton className="h-10 w-10 rounded-lg" />
      <div className="space-y-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-3 w-16" />
      </div>
    </div>
    <Skeleton className="h-16 w-full rounded-lg" />
    <Skeleton className="h-4 w-full" />
    <Skeleton className="h-4 w-3/4" />
  </div>
);

const normalizeDeviceType = (type) => {
  const t = String(type || '').trim().toLowerCase();
  if (t === 'gateway') return 'Gateway';
  if (t === 'temperature' || t.includes('nhiệt')) return 'Temperature';
  if (t === 'power' || t.includes('công suất')) return 'Power';
  if (t === 'vibration' || t.includes('độ rung')) return 'Vibration';
  if (t === 'gps') return 'GPS';
  return 'Temperature';
};

// Định nghĩa ở module-level + React.memo: không tái tạo type mỗi render (tránh remount
// toàn bộ card) và bỏ qua re-render khi props của card không đổi.
const DeviceCard = React.memo(function DeviceCard({ device, isAdmin, onDelete }) {
  const online = device.status === 'online';
  return (
    <div className="bg-card text-card-foreground rounded-xl border border-border overflow-hidden shadow-lg hover:shadow-xl hover:border-primary transition-all duration-200 group">
      {/* Card Header */}
      <div className="p-6 pb-4">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-lg ${online ? 'bg-green-500/20' : 'bg-red-500/20'}`}>
              <Cpu className={`h-6 w-6 ${online ? 'text-green-500' : 'text-red-500'}`} />
            </div>
            <div>
              <h3 className="text-lg font-bold text-foreground group-hover:text-primary transition-colors">
                {device.name}
              </h3>
              <p className="text-muted-foreground text-sm">{device.type}</p>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <Link
              to={`/devices/${device.id}`}
              className="p-2 hover:bg-muted rounded-lg transition-colors duration-200"
              title="View Detail"
              aria-label={`View detail ${device.id}`}
            >
              <ExternalLink className="h-5 w-5 text-muted-foreground hover:text-primary" />
            </Link>
            {isAdmin && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => onDelete(device)}
                className="text-red-400 hover:text-red-300 hover:bg-red-900/40"
                title="Xóa thiết bị"
                aria-label={`Xóa thiết bị ${device.id}`}
              >
                <Trash2 className="h-5 w-5" />
              </Button>
            )}
          </div>
        </div>

        {/* Device ID */}
        <div className="bg-background rounded-lg p-3 mb-4">
          <p className="text-muted-foreground text-xs mb-1">Device ID</p>
          <p className="text-primary font-mono text-sm font-semibold">{device.id}</p>
        </div>

        {/* Location */}
        <div className="flex items-center space-x-2 text-muted-foreground mb-3">
          <MapPin className="h-4 w-4" />
          <span className="text-sm">{device.location}</span>
        </div>

        {/* Last Update */}
        <div className="flex items-center space-x-2 text-muted-foreground mb-4">
          <Clock className="h-4 w-4" />
          <span className="text-xs">{device.lastUpdate}</span>
        </div>

        {isAdmin && (
          <div className="bg-background rounded-lg p-3 mb-4">
            <p className="text-muted-foreground text-xs mb-1">Được phân quyền cho</p>
            {Array.isArray(device.managers) && device.managers.length > 0 ? (
              <div className="space-y-1 max-h-20 overflow-y-auto">
                {device.managers.slice(0, 3).map((m) => (
                  <p key={m.user_id} className="text-foreground/90 text-xs">
                    {m.fullname} <span className="text-muted-foreground">@{m.username}</span>
                  </p>
                ))}
                {device.managers.length > 3 && (
                  <p className="text-muted-foreground text-[11px]">
                    +{device.managers.length - 3} user khác
                  </p>
                )}
              </div>
            ) : (
              <p className="text-muted-foreground text-xs">Chưa phân quyền cho user nào</p>
            )}
          </div>
        )}

        {/* Current Value */}
        <div className="bg-background rounded-lg p-3 mb-4">
          <p className="text-muted-foreground text-xs mb-1">Current Reading</p>
          {device.type === 'GPS' ? (
            <div className="text-foreground">
              <p className="font-bold text-sm mb-1">X: <span className="text-primary">{Number.isFinite(Number(device.x)) ? Number(device.x).toFixed(2) : device.x}</span></p>
              <p className="font-bold text-sm">Y: <span className="text-primary">{Number.isFinite(Number(device.y)) ? Number(device.y).toFixed(2) : device.y}</span></p>
            </div>
          ) : (
            <p className="text-foreground font-bold text-2xl">
              {device.value} <span className="text-muted-foreground text-base">{device.unit}</span>
            </p>
          )}
        </div>
      </div>

      {/* Card Footer — chỉ hiển thị trạng thái (read-only).
          FE chưa có khả năng điều khiển bật/tắt thiết bị thật nên không render nút toggle. */}
      <div className="px-6 py-4 bg-background border-t border-border flex items-center">
        <StatusBadge status={device.status} />
      </div>
    </div>
  );
});

const Devices = () => {
  const { isAdmin } = useAuth();
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState('');
  const [deleteError, setDeleteError] = useState('');
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    // JWT đi qua WebSocket subprotocol để không lộ trong access log.
    const ws = openWebSocket('/ws/global');

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setDevices((prevDevices) =>
        prevDevices.map((d) =>
          String(d.id ?? d.device_id) === String(data.device_id)
            ? { ...d, ...data }
            : d
        )
      );
    };

    return () => ws.close();
  }, []);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      setLoadError('');
      try {
        const path = isAdmin() ? '/api/devices' : '/api/devices/my';
        const list = await apiFetch(path);
        let normalizedList = Array.isArray(list) ? list : [];

        // Admin view: enrich each device with assigned users (RBAC) for quick visibility on cards.
        if (isAdmin()) {
          try {
            const users = await apiFetch('/api/users');
            const userList = Array.isArray(users) ? users : [];
            const managerMap = new Map();

            const usersHaveAuthorizedField = userList.every((u) =>
              Array.isArray(u.authorized_devices)
            );

            if (usersHaveAuthorizedField) {
              // Preferred path: invert /users[].authorized_devices -> device_id => users[]
              for (const u of userList) {
                for (const d of u.authorized_devices || []) {
                  const key = String(d.device_id);
                  const arr = managerMap.get(key) || [];
                  arr.push({
                    user_id: u.user_id,
                    username: u.username,
                    fullname: u.fullname,
                  });
                  managerMap.set(key, arr);
                }
              }
            } else {
              // Fallback path: older backend (no authorized_devices in /users)
              const userById = new Map(userList.map((u) => [String(u.user_id), u]));
              await Promise.all(
                normalizedList.map(async (d) => {
                  const deviceId = d.device_id ?? d.id;
                  if (deviceId == null) return;
                  try {
                    const auths = await apiFetch(
                      `/api/authorizations?device_id=${encodeURIComponent(deviceId)}`
                    );
                    const arr = (Array.isArray(auths) ? auths : []).map((a) => {
                      const u = userById.get(String(a.user_id));
                      return {
                        user_id: a.user_id,
                        username: u?.username ?? `user_${a.user_id}`,
                        fullname: u?.fullname ?? `User ${a.user_id}`,
                      };
                    });
                    managerMap.set(String(deviceId), arr);
                  } catch {
                    managerMap.set(String(deviceId), []);
                  }
                })
              );
            }

            normalizedList = normalizedList.map((d) => {
              const deviceId = d.device_id ?? d.id;
              const managersRaw = managerMap.get(String(deviceId)) || [];
              const dedup = new Map();
              for (const m of managersRaw) dedup.set(String(m.user_id), m);
              return { ...d, managers: Array.from(dedup.values()) };
            });
          } catch {
            // Keep devices list visible even if manager enrichment fails.
            normalizedList = normalizedList.map((d) => ({ ...d, managers: [] }));
          }
        }

        if (!mounted) return;
        setDevices(normalizedList);
      } catch (e) {
        if (!mounted) return;
        // Không fallback mock data trong prod (tránh hiển thị thiết bị giả gây hiểu nhầm).
        setLoadError(e.message || 'Không tải được danh sách thiết bị');
        setDevices([]);
      } finally {
        if (!mounted) return;
        setLoading(false);
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, [isAdmin]);

  const handleAddDevice = (newDevice) => {
    // Optimistically append created device; next page refresh will sync from API.
    setDevices((prev) => [...prev, newDevice]);
    setShowAddModal(false);
  };

  const handleDeleteDevice = async () => {
    if (deleteConfirm !== 'OK') {
      setDeleteError('Nhập chính xác OK (chữ in hoa)');
      return;
    }
    const rawId = deleteTarget?.device_id ?? deleteTarget?.id;
    if (rawId == null) return;
    setDeleteError('');
    setDeleting(true);
    try {
      await apiFetch(`/api/devices/${encodeURIComponent(rawId)}`, { method: 'DELETE' });
      setDeleteTarget(null);
      setDeleteConfirm('');
      setDevices((prev) =>
        prev.filter((d) => String(d.device_id ?? d.id) !== String(rawId))
      );
    } catch (err) {
      const msg = String(err?.message || '').toLowerCase();
      if (msg.includes('method not allowed')) {
        setDeleteError('Backend hiện tại chưa deploy endpoint xóa thiết bị (DELETE /api/devices/{id}).');
      } else {
        setDeleteError(err.message || 'Xóa thiết bị thất bại');
      }
    } finally {
      setDeleting(false);
    }
  };

  const normalizedDevices = useMemo(() => {
    // Normalize data shape between mock and API:
    // - mock uses { id, name, type, location, lastUpdate, value, ... }
    // - API returns static fields only; live readings come from MQTT/payload later (not stored in DB).
    return devices.map((d) => {
      const id = d.id ?? d.device_id;
      const name = d.name ?? d.devicename ?? `Device ${id}`;
      const type = normalizeDeviceType(d.device_type ?? d.type);
      const location = d.location ?? '—';
      const lastUpdate = d.lastUpdate ?? '—';
      const value = d.value ?? '—';
      const unit = d.unit ?? '';
      const coordX = d.x ?? d.longitude ?? d.lon ?? d.long ?? null;
      const coordY = d.y ?? d.latitude ?? d.lat ?? null;
      const xVal = coordX == null ? '—' : coordX;
      const yVal = coordY == null ? '—' : coordY;
      // Chuẩn hoá status (active/deactive từ API hoặc online/offline từ mock) → 'online'|'offline'
      // để DeviceCard so sánh nhất quán.
      const status = toUiStatus(d.status);
      return { ...d, id: String(id), name, type, location, lastUpdate, value, unit, x: xVal, y: yVal, status };
    });
  }, [devices]);

  const filteredDevices = normalizedDevices.filter((device) => {
    const q = searchTerm.toLowerCase();
    return (
      device.name.toLowerCase().includes(q) ||
      device.id.toLowerCase().includes(q) ||
      device.location.toLowerCase().includes(q)
    );
  });

  const admin = isAdmin();
  const handleDeleteRequest = useCallback((device) => {
    setDeleteTarget(device);
    setDeleteConfirm('');
    setDeleteError('');
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Devices"
        description="Manage and monitor your IoT devices"
        actions={
          <span className="text-muted-foreground">
            Total: <span className="text-foreground font-bold">{normalizedDevices.length}</span>
          </span>
        }
      />

      {loadError && (
        <div className="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-200 text-sm">{loadError}</div>
      )}

      {/* Search Bar */}
      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
          <Search className="h-5 w-5 text-muted-foreground" />
        </div>
        <input
          type="text"
          placeholder="Search devices by name, ID, or location..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-11 pr-4 py-3 bg-card border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all duration-200"
        />
      </div>

      {/* Devices Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading
          ? Array.from({ length: 3 }).map((_, i) => <DeviceCardSkeleton key={i} />)
          : filteredDevices.map(device => (
              <DeviceCard
                key={device.id}
                device={device}
                isAdmin={admin}
                onDelete={handleDeleteRequest}
              />
            ))
        }
      </div>

      {/* No Results */}
      {filteredDevices.length === 0 && (
        <div className="text-center py-12">
          <Cpu className="h-16 w-16 text-muted-foreground/60 mx-auto mb-4" />
          <p className="text-muted-foreground text-lg">No devices found</p>
          <p className="text-muted-foreground text-sm">
            {loading
              ? 'Đang tải...'
              : isAdmin()
                ? 'Try adjusting your search criteria'
                : 'Bạn chưa được cấp quyền truy cập thiết bị nào (RBAC)'}
          </p>
        </div>
      )}

      {/* Floating Action Button - Admin Only */}
      {isAdmin() && (
        <button
          onClick={() => setShowAddModal(true)}
          className="fixed bottom-8 right-8 w-14 h-14 bg-primary hover:bg-primary/90 text-primary-foreground rounded-full shadow-2xl shadow-blue-500/50 hover:shadow-blue-500/70 transition-all duration-200 flex items-center justify-center group hover:scale-110 z-40"
          title="Add New Device"
        >
          <Plus className="h-7 w-7" />
        </button>
      )}

      {/* Add Device Modal */}
      {showAddModal && (
        <AddDeviceModal
          onClose={() => setShowAddModal(false)}
          onAdd={handleAddDevice}
        />
      )}

      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          // Đóng (ESC / click overlay / Cancel) → reset state. Không cho đóng khi đang xoá.
          if (!open && !deleting) {
            setDeleteTarget(null);
            setDeleteConfirm('');
            setDeleteError('');
          }
        }}
      >
        <AlertDialogContent className="border-red-900/50">
          <AlertDialogHeader>
            <AlertDialogTitle>Xác nhận xóa thiết bị</AlertDialogTitle>
            <AlertDialogDescription>
              Thao tác này xóa thiết bị và các bản ghi phân quyền liên quan. Không thể hoàn tác.
            </AlertDialogDescription>
          </AlertDialogHeader>

          {deleteTarget && (
            <ul className="text-foreground/90 text-sm space-y-1 list-disc list-inside">
              <li>
                <span className="text-muted-foreground">Tên:</span>{' '}
                {deleteTarget.name ?? deleteTarget.devicename ?? '—'}
              </li>
              <li>
                <span className="text-muted-foreground">Device ID:</span>{' '}
                {deleteTarget.device_id ?? deleteTarget.id}
              </li>
            </ul>
          )}

          <div>
            <p className="text-amber-200/90 text-xs mb-2">
              Nhập <strong className="text-foreground">OK</strong> (chữ in hoa) để xác nhận.
            </p>
            <input
              type="text"
              value={deleteConfirm}
              onChange={(e) => setDeleteConfirm(e.target.value)}
              placeholder="OK"
              aria-label="Nhập OK để xác nhận xóa"
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-foreground font-mono"
            />
            {deleteError && <p className="text-red-400 text-sm mt-2">{deleteError}</p>}
          </div>

          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Hủy</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleting}
              className="bg-destructive text-white hover:bg-destructive/90"
              onClick={(e) => {
                // Ngăn AlertDialogAction tự đóng dialog: tự xử lý đóng trong handleDeleteDevice
                // (chỉ đóng khi xoá thành công; nếu lỗi/confirm sai phải giữ dialog để hiện lỗi).
                e.preventDefault();
                handleDeleteDevice();
              }}
            >
              {deleting ? 'Đang xóa...' : 'Xóa thiết bị'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default Devices;
