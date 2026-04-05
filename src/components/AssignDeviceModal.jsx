import React, { useEffect, useMemo, useState } from 'react';
import { X } from 'lucide-react';
import { apiFetch } from '../lib/api';

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function plusDaysIso(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export default function AssignDeviceModal({ user, currentAdmin, onClose, onSuccess }) {
  const [devices, setDevices] = useState([]);
  const [assignedDeviceIds, setAssignedDeviceIds] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const [deviceId, setDeviceId] = useState('');
  const [grantedAt, setGrantedAt] = useState(() => todayIso());
  const [expiredAt, setExpiredAt] = useState(() => plusDaysIso(30));
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      setLoadError('');
      try {
        const [allDevices, auths] = await Promise.all([
          apiFetch('/api/devices'),
          apiFetch(`/api/authorizations?user_id=${encodeURIComponent(user.user_id)}`),
        ]);
        if (!mounted) return;
        const list = Array.isArray(allDevices) ? allDevices : [];
        setDevices(list);

        const existing = new Set(
          (Array.isArray(auths) ? auths : []).map((a) => String(a.device_id))
        );
        setAssignedDeviceIds(existing);
      } catch (e) {
        if (!mounted) return;
        setLoadError(e.message || 'Không tải được danh sách thiết bị');
      } finally {
        if (!mounted) return;
        setLoading(false);
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, [user.user_id]);

  const availableDevices = useMemo(() => {
    return devices.filter((d) => !assignedDeviceIds.has(String(d.device_id)));
  }, [devices, assignedDeviceIds]);

  useEffect(() => {
    if (!deviceId && availableDevices.length > 0) {
      setDeviceId(String(availableDevices[0].device_id));
    }
  }, [availableDevices, deviceId]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitError('');
    if (!deviceId) {
      setSubmitError('Vui lòng chọn thiết bị');
      return;
    }
    if (!grantedAt || !expiredAt) {
      setSubmitError('Vui lòng nhập đủ ngày cấp và ngày hết hạn');
      return;
    }
    if (expiredAt < grantedAt) {
      setSubmitError('expired_at không được trước granted_at');
      return;
    }

    setSubmitting(true);
    try {
      // granted_by: VARCHAR(45) — lưu định danh admin (username/fullname).
      // Nếu bạn muốn lưu admin_id (INT), hãy đổi type cột granted_by sang INT và gửi user_id.
      const grantedBy =
        currentAdmin?.username ??
        currentAdmin?.fullname ??
        String(currentAdmin?.user_id ?? 'admin');

      await apiFetch('/api/authorizations', {
        method: 'POST',
        body: JSON.stringify({
          device_id: Number(deviceId),
          user_id: Number(user.user_id),
          granted_at: grantedAt,
          granted_by: grantedBy,
          expired_at: expiredAt,
        }),
      });
      onSuccess?.();
      onClose();
    } catch (err) {
      setSubmitError(err.message || 'Phân quyền thất bại');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      <div className="bg-slate-800 border border-slate-700 rounded-xl max-w-lg w-full shadow-2xl">
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-white truncate">Phân quyền thiết bị</h2>
            <p className="text-slate-400 text-sm truncate">
              User: <span className="text-slate-200 font-semibold">{user.fullname}</span> (@{user.username})
            </p>
            {currentAdmin?.fullname && (
              <p className="text-slate-500 text-xs">
                Admin: <span className="text-slate-300">{currentAdmin.fullname}</span>
              </p>
            )}
          </div>
          <button type="button" onClick={onClose} className="p-2 rounded-lg hover:bg-slate-700 text-slate-400">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {loadError && (
            <div className="p-3 rounded-lg bg-red-900/30 border border-red-700 text-red-200 text-sm">{loadError}</div>
          )}

          <div>
            <label className="block text-sm text-slate-300 mb-1">Thiết bị</label>
            <select
              value={deviceId}
              disabled={loading || availableDevices.length === 0}
              onChange={(e) => setDeviceId(e.target.value)}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white disabled:opacity-50"
            >
              {availableDevices.map((d) => (
                <option key={d.device_id} value={String(d.device_id)}>
                  {d.devicename ?? `Device ${d.device_id}`} (ID: {d.device_id})
                </option>
              ))}
              {availableDevices.length === 0 && <option value="">Không còn thiết bị để cấp</option>}
            </select>
            <p className="text-slate-500 text-xs mt-1">Chỉ hiển thị các thiết bị chưa được cấp cho user này.</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-slate-300 mb-1">granted_at</label>
              <input
                type="date"
                value={grantedAt}
                onChange={(e) => setGrantedAt(e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-300 mb-1">expired_at</label>
              <input
                type="date"
                value={expiredAt}
                onChange={(e) => setExpiredAt(e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white"
              />
            </div>
          </div>

          {submitError && (
            <div className="p-3 rounded-lg bg-red-900/30 border border-red-700 text-red-200 text-sm">{submitError}</div>
          )}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={submitting || loading || availableDevices.length === 0}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50"
            >
              {submitting ? 'Đang lưu...' : 'Submit'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

