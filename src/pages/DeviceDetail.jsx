import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  ArrowLeft,
  Cpu,
  MapPin,
  Clock,
  Edit2,
  Eye,
  EyeOff,
  Wifi,
  WifiOff,
  Activity,
  Gauge,
  Maximize2,
  Minimize2,
  Zap,
  Waves,
  Users,
} from 'lucide-react';
import { mockDevices, generateDeviceHistory } from '../data/mockData';
import { apiFetch } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import ChangePasswordModal from '../components/ChangePasswordModal';

function resolveWsBase() {
  const envBase = String(import.meta.env.VITE_WS_URL ?? '').trim();
  if (envBase) return envBase.replace(/\/$/, '');
  if (typeof window === 'undefined') return '';
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}`;
}

const WS_BASE = resolveWsBase();

function normalizeDeviceType(type) {
  const t = String(type || '').trim().toLowerCase();
  if (t === 'temperature' || t.includes('nhiệt')) return 'Temperature';
  if (t === 'power' || t.includes('công suất')) return 'Power';
  if (t === 'vibration' || t.includes('độ rung')) return 'Vibration';
  return 'Temperature';
}

function getDeviceMetrics(type) {
  const normalized = normalizeDeviceType(type);
  if (normalized === 'Power') {
    return [
      { key: 'voltage', title: 'Voltage (V)', lineName: 'Voltage', color: '#a855f7', icon: Zap },
      { key: 'current', title: 'Current (A)', lineName: 'Current', color: '#3b82f6', icon: Gauge },
    ];
  }
  if (normalized === 'Vibration') {
    return [
      { key: 'vibration', title: 'Vibration (mm/s)', lineName: 'Vibration', color: '#10b981', icon: Waves },
    ];
  }
  return [
    { key: 'temperature', title: 'Temperature (°C)', lineName: 'Temperature', color: '#ef4444', icon: Activity },
  ];
}

/** Map API device row to the shape used by this page (previously mock-only). */
function mapApiDeviceToUi(d) {
  const id = String(d.device_id);
  const online = String(d.status || '').toLowerCase() === 'active';
  const normalizedType = normalizeDeviceType(d.device_type);
  return {
    id,
    name: d.devicename || `Device ${id}`,
    type: normalizedType,
    location: d.location ?? '—',
    lastUpdate: '—',
    value: '—',
    unit: '',
    password: d.password != null && String(d.password).length > 0 ? String(d.password) : '********',
    status: online ? 'online' : 'offline',
  };
}

/** ISO date → dd/mm/yyyy */
function isoDateToDisplay(iso) {
  if (!iso) return '—';
  const s = String(iso).slice(0, 10);
  const [y, m, d] = s.split('-');
  if (!y || !m || !d) return '—';
  return `${d}/${m}/${y}`;
}

function formatTime(ts) {
  try {
    return new Date(ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return String(ts);
  }
}

function capPush(arr, item, max = 80) {
  const next = [...arr, item];
  return next.length > max ? next.slice(next.length - max) : next;
}

function normalizeEventTsToMs(ts) {
  const n = Number(ts);
  if (!Number.isFinite(n)) return Date.now();
  return n > 1_000_000_000_000 ? n : n * 1000;
}

function mapHistoryToSeries(item) {
  const ts = item?.ts ? Number(item.ts) * 1000 : Date.now();
  return {
    id: `${item?.device_id || 'd'}-${item?.ts_iso || ts}`,
    time: formatTime(ts),
    timestamp: item?.ts_iso || new Date(ts).toISOString(),
    temperature: Number.isFinite(Number(item?.temperature)) ? Number(item.temperature) : 0,
    vibration: Number.isFinite(Number(item?.vibration)) ? Number(item.vibration) : 0,
    voltage: Number.isFinite(Number(item?.voltage)) ? Number(item.voltage) : 0,
    current: Number.isFinite(Number(item?.current)) ? Number(item.current) : 0,
  };
}

const DeviceDetail = () => {
  const { deviceId } = useParams();
  const navigate = useNavigate();
  const { user, isAdmin } = useAuth();
  const [device, setDevice] = useState(null);
  /** Payload API gốc (authorized_users, user_device_asignment_id cho admin) */
  const [apiDetail, setApiDetail] = useState(null);
  const [loadingDevice, setLoadingDevice] = useState(true);
  const [activeTab, setActiveTab] = useState('account');
  const [showPassword, setShowPassword] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [assignmentId, setAssignmentId] = useState('');
  const [assignmentSaving, setAssignmentSaving] = useState(false);
  const [assignmentError, setAssignmentError] = useState('');
  const [assignmentOk, setAssignmentOk] = useState(false);
  const [realtimeSeries, setRealtimeSeries] = useState([]);
  const [historyRows, setHistoryRows] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [fullscreenMetric, setFullscreenMetric] = useState(null);
  const [topics, setTopics] = useState([]);
  const [topicInput, setTopicInput] = useState('');
  const [topicBusy, setTopicBusy] = useState(false);
  const [topicError, setTopicError] = useState('');
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      if (!deviceId) return;
      setLoadingDevice(true);
      setApiDetail(null);
      try {
        const data = await apiFetch(`/api/devices/${encodeURIComponent(deviceId)}`);
        if (!cancelled) {
          setApiDetail(data);
          setDevice(mapApiDeviceToUi(data));
          if (user?.role === 'admin' && data && data.user_device_asignment_id != null) {
            setAssignmentId(String(data.user_device_asignment_id));
          } else {
            setAssignmentId('');
          }
        }
      } catch {
        const mock = mockDevices.find((d) => String(d.id) === String(deviceId));
        if (!cancelled) {
          setDevice(mock ?? null);
          setApiDetail(null);
        }
      } finally {
        if (!cancelled) setLoadingDevice(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [deviceId, user?.role]);

  useEffect(() => {
    if (!deviceId) return;

    let cancelled = false;
    setHistoryLoading(true);
    setHistoryError('');
    const preferredTopic = String(apiDetail?.topic || '').trim();

    apiFetch(`/api/mqtt/history?minutes=30&device_id=${encodeURIComponent(deviceId)}`)
      .then(async (data) => {
        if (cancelled) return;
        let items = Array.isArray(data?.items) ? data.items : [];

        // Fallback: nhiều node gửi device_id kiểu chuỗi (vd ESP32_WS_01)
        // không khớp device_id số trong DB. Khi đó lọc theo topic của thiết bị.
        if (items.length === 0 && preferredTopic) {
          try {
            const all = await apiFetch('/api/mqtt/history?minutes=30');
            const allItems = Array.isArray(all?.items) ? all.items : [];
            items = allItems.filter((x) => String(x?.topic || '').trim() === preferredTopic);
          } catch {
            // keep original empty list
          }
        }

        const mapped = items.map(mapHistoryToSeries);
        setHistoryRows(mapped);
        setRealtimeSeries(mapped.slice(-80));
      })
      .catch((err) => {
        if (cancelled) return;
        setHistoryError(err?.message || 'Khong tai duoc lich su 30 phut');
        const fallback = generateDeviceHistory(device?.id ?? deviceId).map((row) => ({
          id: row.id,
          time: row.timestamp,
          timestamp: row.timestamp,
          temperature: Number(row.parameterValue) || 0,
          vibration: Number(row.parameterValue) || 0,
          voltage: Number(row.parameterValue) || 0,
          current: Number(row.parameterValue) || 0,
        }));
        setHistoryRows(fallback);
        setRealtimeSeries(fallback.slice(-80));
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [deviceId, device?.id, apiDetail?.topic]);

  useEffect(() => {
    if (!isAdmin()) return;
    let cancelled = false;

    apiFetch('/api/mqtt/topics')
      .then((data) => {
        if (cancelled) return;
        setTopics(Array.isArray(data?.items) ? data.items : []);
      })
      .catch(() => {
        if (!cancelled) setTopics([]);
      });

    return () => {
      cancelled = true;
    };
  }, [isAdmin]);

  useEffect(() => {
    if (activeTab !== 'dashboard') return undefined;

    const preferredTopic = String(apiDetail?.topic || '').trim();
    const expectedDeviceId = String(deviceId || '').trim();

    // WebSocket init (Device-specific dashboard)
    // Connect to a device-specific channel/room by deviceId.
    // Expected payload examples:
    // - { ts, deviceId, current, voltage, temperature, vibration }
    // - { ts, current, voltage, temperature, vibration }  (implicit current device)
    // Nếu có topic, dùng global channel rồi lọc theo topic để tránh lệch device_id DB vs payload.
    const url = WS_BASE
      ? (preferredTopic ? `${WS_BASE}/ws/global` : `${WS_BASE}/ws/devices/${deviceId}`)
      : null;
    if (!url) return undefined;

    let closedByEffect = false;

    const connect = () => {
      if (closedByEffect) return;

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onmessage = (ev) => {
        // Parse and normalize chart payload
        let msg = null;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }

        const ts = msg.ts ?? Date.now();
        const topic = String(msg.topic || '').trim();
        const msgDeviceId = String(msg.device_id ?? msg.deviceId ?? '').trim();
        const matchedByTopic = preferredTopic && topic === preferredTopic;
        const matchedByDeviceId = msgDeviceId && expectedDeviceId && msgDeviceId === expectedDeviceId;

        if (!matchedByTopic && !matchedByDeviceId) {
          return;
        }

        const tsMs = normalizeEventTsToMs(ts);
        const time = formatTime(tsMs);

        const current = Number(msg.current);
        const voltage = Number(msg.voltage);
        const temperature = Number(msg.temperature);
        const vibration = Number(msg.vibration ?? msg.vibration_mms ?? msg.vibrationMmS);

        setRealtimeSeries((prev) =>
          capPush(prev, {
            time,
            current: Number.isFinite(current) ? current : 0,
            voltage: Number.isFinite(voltage) ? voltage : 0,
            temperature: Number.isFinite(temperature) ? temperature : 0,
            vibration: Number.isFinite(vibration) ? vibration : 0,
          })
        );
      };

      ws.onclose = () => {
        if (closedByEffect) return;
        reconnectTimerRef.current = setTimeout(connect, 1200);
      };
    };

    connect();

    return () => {
      // WebSocket cleanup
      closedByEffect = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [activeTab, deviceId, apiDetail?.topic]);

  useEffect(() => {
    if (!fullscreenMetric) return undefined;
    const onKeydown = (event) => {
      if (event.key === 'Escape') setFullscreenMetric(null);
    };
    window.addEventListener('keydown', onKeydown);
    return () => window.removeEventListener('keydown', onKeydown);
  }, [fullscreenMetric]);

  useEffect(() => {
    if (activeTab !== 'dashboard' && fullscreenMetric) {
      setFullscreenMetric(null);
    }
  }, [activeTab, fullscreenMetric]);

  if (loadingDevice) {
    return (
      <div className="text-center py-12">
        <Cpu className="h-16 w-16 text-slate-600 mx-auto mb-4 animate-pulse" />
        <p className="text-slate-400 text-lg">Loading device…</p>
      </div>
    );
  }

  if (!device) {
    return (
      <div className="text-center py-12">
        <Cpu className="h-16 w-16 text-slate-600 mx-auto mb-4" />
        <p className="text-slate-400 text-lg">Device not found</p>
        <button
          onClick={() => navigate('/devices')}
          className="mt-4 px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors duration-200"
        >
          Back to Devices
        </button>
      </div>
    );
  }

  const maskPassword = (password) => {
    const s = password != null ? String(password) : '';
    return '•'.repeat(Math.max(s.length, 8));
  };
  const deviceMetrics = getDeviceMetrics(device.type);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-4">
        <button
          onClick={() => navigate('/devices')}
          className="p-2 hover:bg-slate-800 rounded-lg transition-colors duration-200"
        >
          <ArrowLeft className="h-6 w-6 text-slate-400" />
        </button>
        <div className="flex-1">
          <h1 className="text-3xl font-bold text-white mb-2">{device.name}</h1>
          <div className="flex items-center space-x-4 text-slate-400">
            <span className="flex items-center space-x-2">
              <MapPin className="h-4 w-4" />
              <span>{device.location}</span>
            </span>
            <span className="flex items-center space-x-2">
              <Clock className="h-4 w-4" />
              <span>{device.lastUpdate}</span>
            </span>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          {device.status === 'online' ? (
            <>
              <Wifi className="h-5 w-5 text-green-500" />
              <span className="text-green-500 font-semibold">ONLINE</span>
            </>
          ) : (
            <>
              <WifiOff className="h-5 w-5 text-red-500" />
              <span className="text-red-500 font-semibold">OFFLINE</span>
            </>
          )}
        </div>
      </div>

      {/* Device Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
          <div className="flex items-center space-x-3 mb-4">
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <Cpu className="h-5 w-5 text-blue-500" />
            </div>
            <p className="text-slate-400 text-sm font-medium">Device ID</p>
          </div>
          <p className="text-blue-400 font-mono text-lg font-bold">{device.id}</p>
        </div>

        <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
          <div className="flex items-center space-x-3 mb-4">
            <div className="p-2 bg-purple-500/20 rounded-lg">
              <Activity className="h-5 w-5 text-purple-500" />
            </div>
            <p className="text-slate-400 text-sm font-medium">Device Type</p>
          </div>
          <p className="text-white text-lg font-bold">{device.type}</p>
        </div>

        <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
          <div className="flex items-center space-x-3 mb-4">
            <div className={`p-2 rounded-lg ${
              device.status === 'online' ? 'bg-green-500/20' : 'bg-red-500/20'
            }`}>
              <Activity className={`h-5 w-5 ${
                device.status === 'online' ? 'text-green-500' : 'text-red-500'
              }`} />
            </div>
            <p className="text-slate-400 text-sm font-medium">Current Reading</p>
          </div>
          <p className="text-white text-2xl font-bold">
            {device.value} <span className="text-slate-400 text-base">{device.unit}</span>
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
        {/* Tab Headers */}
        <div className="flex border-b border-slate-700">
          <button
            onClick={() => setActiveTab('account')}
            className={`flex-1 px-6 py-4 font-semibold transition-colors duration-200 ${
              activeTab === 'account'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:bg-slate-700 hover:text-white'
            }`}
          >
            Account
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`flex-1 px-6 py-4 font-semibold transition-colors duration-200 ${
              activeTab === 'history'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:bg-slate-700 hover:text-white'
            }`}
          >
            History
          </button>
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`flex-1 px-6 py-4 font-semibold transition-colors duration-200 ${
              activeTab === 'dashboard'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:bg-slate-700 hover:text-white'
            }`}
          >
            Dashboard
          </button>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {activeTab === 'account' && (
            <div className="space-y-6">
              {/* Device ID Section */}
              <div className="bg-slate-900 rounded-lg p-6 border border-slate-700">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-2">
                    <Cpu className="h-5 w-5 text-blue-500" />
                    <h3 className="text-lg font-semibold text-white">Device Credentials</h3>
                  </div>
                </div>
                
                <div className="space-y-4">
                  <div>
                    <label className="block text-slate-400 text-sm mb-2">Device ID</label>
                    <div className="bg-slate-800 border border-slate-600 rounded-lg px-4 py-3">
                      <p className="text-blue-400 font-mono font-semibold">{device.id}</p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-slate-400 text-sm mb-2">Password</label>
                    <div className="flex space-x-2">
                      <div className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-4 py-3 flex items-center justify-between">
                        <p className="text-white font-mono">
                          {showPassword ? device.password : maskPassword(device.password)}
                        </p>
                        <button
                          onClick={() => setShowPassword(!showPassword)}
                          className="ml-2 p-1 hover:bg-slate-700 rounded transition-colors duration-200"
                        >
                          {showPassword ? (
                            <EyeOff className="h-4 w-4 text-slate-400" />
                          ) : (
                            <Eye className="h-4 w-4 text-slate-400" />
                          )}
                        </button>
                      </div>
                      <button
                        onClick={() => setShowPasswordModal(true)}
                        className="px-4 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors duration-200 flex items-center space-x-2"
                      >
                        <Edit2 className="h-4 w-4" />
                        <span>Edit</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Device Information */}
              <div className="bg-slate-900 rounded-lg p-6 border border-slate-700">
                <h3 className="text-lg font-semibold text-white mb-4">Device Information</h3>
                
                <div className="space-y-3">
                  <div className="flex justify-between py-2 border-b border-slate-700">
                    <span className="text-slate-400">Name</span>
                    <span className="text-white font-medium">{device.name}</span>
                  </div>
                  <div className="flex justify-between py-2 border-b border-slate-700">
                    <span className="text-slate-400">Type</span>
                    <span className="text-white font-medium">{device.type}</span>
                  </div>
                  <div className="flex justify-between py-2 border-b border-slate-700">
                    <span className="text-slate-400">Location</span>
                    <span className="text-white font-medium">{device.location}</span>
                  </div>
                  <div className="flex justify-between py-2">
                    <span className="text-slate-400">Status</span>
                    <span className={`font-semibold ${
                      device.status === 'online' ? 'text-green-500' : 'text-red-500'
                    }`}>
                      {device.status.toUpperCase()}
                    </span>
                  </div>
                </div>
              </div>

              {/* User được phân quyền RBAC — mọi người có quyền xem chi tiết đều thấy */}
              {apiDetail && Array.isArray(apiDetail.authorized_users) && (
                <div className="bg-slate-900 rounded-lg p-6 border border-slate-700">
                  <div className="flex items-center space-x-2 mb-4">
                    <Users className="h-5 w-5 text-cyan-400" />
                    <h3 className="text-lg font-semibold text-white">Người được phân quyền truy cập</h3>
                  </div>
                  {apiDetail.authorized_users.length === 0 ? (
                    <p className="text-slate-500 text-sm">Chưa có user nào được gán quyền (RBAC).</p>
                  ) : (
                    <ul className="space-y-3">
                      {apiDetail.authorized_users.map((u) => (
                        <li
                          key={u.user_id}
                          className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-800 pb-3 last:border-0 last:pb-0"
                        >
                          <div>
                            <p className="text-white font-medium">{u.fullname}</p>
                            <p className="text-slate-500 text-sm">
                              @{u.username} · ID <span className="font-mono text-slate-400">{u.user_id}</span>
                            </p>
                          </div>
                          <p className="text-slate-400 text-xs shrink-0">
                            Hết hạn quyền:{' '}
                            <span className="text-slate-300">{isoDateToDisplay(u.expired_at)}</span>
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {/* Gán tài khoản legacy (cột user_device_asignment_id) — chỉ admin */}
              {isAdmin() && apiDetail && (
                <div className="bg-slate-900 rounded-lg p-6 border border-amber-900/40">
                  <h3 className="text-lg font-semibold text-white mb-1">Gán tài khoản (legacy)</h3>
                  <p className="text-slate-500 text-sm mb-4">
                    Trường <span className="font-mono text-slate-400">user_device_asignment_id</span> trên bản ghi
                    thiết bị. Chỉ admin xem và chỉnh sửa.
                  </p>
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      const n = parseInt(String(assignmentId).trim(), 10);
                      setAssignmentError('');
                      setAssignmentOk(false);
                      if (Number.isNaN(n) || n < 0) {
                        setAssignmentError('Nhập số nguyên không âm (ID user gán thiết bị).');
                        return;
                      }
                      setAssignmentSaving(true);
                      apiFetch(`/api/devices/${encodeURIComponent(deviceId)}`, {
                        method: 'PATCH',
                        body: JSON.stringify({ user_device_asignment_id: n }),
                      })
                        .then(() => {
                          setApiDetail((prev) =>
                            prev ? { ...prev, user_device_asignment_id: n } : prev
                          );
                          setAssignmentOk(true);
                        })
                        .catch((err) => {
                          setAssignmentError(err.message || 'Lưu thất bại');
                        })
                        .finally(() => setAssignmentSaving(false));
                    }}
                    className="flex flex-col sm:flex-row gap-3 sm:items-end"
                  >
                    <div className="flex-1">
                      <label className="block text-slate-400 text-sm mb-2">User ID gán thiết bị</label>
                      <input
                        type="number"
                        min={0}
                        value={assignmentId}
                        onChange={(e) => setAssignmentId(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-600 rounded-lg px-4 py-3 text-white font-mono"
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={assignmentSaving}
                      className="px-6 py-3 bg-amber-600 hover:bg-amber-700 text-white rounded-lg disabled:opacity-50"
                    >
                      {assignmentSaving ? 'Đang lưu...' : 'Lưu'}
                    </button>
                  </form>
                  {assignmentError && (
                    <p className="text-red-400 text-sm mt-2">{assignmentError}</p>
                  )}
                  {assignmentOk && !assignmentError && (
                    <p className="text-emerald-400 text-sm mt-2">Đã cập nhật.</p>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === 'history' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">Device History</h3>
                <span className="text-slate-400 text-sm">{historyRows.length} records (30 phut)</span>
              </div>
              {historyLoading && (
                <div className="p-3 rounded-lg bg-slate-900 border border-slate-700 text-slate-300 text-sm">
                  Dang tai lich su tu InfluxDB...
                </div>
              )}
              {historyError && (
                <div className="p-3 rounded-lg bg-amber-900/30 border border-amber-700 text-amber-200 text-sm">
                  {historyError}
                </div>
              )}

              {/* History Table */}
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="bg-slate-900 border-b border-slate-700">
                      <th className="px-6 py-4 text-left text-sm font-semibold text-slate-300">
                        #
                      </th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-slate-300">
                        Parameter Value
                      </th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-slate-300">
                        Timestamp
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700">
                    {historyRows.map((record, idx) => (
                      <tr key={record.id} className="hover:bg-slate-900 transition-colors duration-150">
                        <td className="px-6 py-4 text-slate-400 text-sm">
                          {idx + 1}
                        </td>
                        <td className="px-6 py-4 text-white font-medium">
                          {`T=${record.temperature.toFixed(2)}°C | Vb=${record.vibration.toFixed(2)}mm/s | U=${record.voltage.toFixed(2)}V | I=${record.current.toFixed(2)}A`}
                        </td>
                        <td className="px-6 py-4 text-slate-400 text-sm">
                          {record.timestamp}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'dashboard' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-white">Device Dashboard</h3>
                <p className="text-slate-400 text-sm">
                  Real-time charts (30-minute history + live) for <span className="text-blue-400 font-mono font-semibold">{deviceId}</span>
                </p>
                {!WS_BASE && (
                  <div className="mt-3 p-3 rounded-lg bg-amber-900/30 border border-amber-700 text-amber-200 text-sm">
                    Missing <span className="font-semibold">VITE_WS_URL</span>. WebSocket will not connect.
                  </div>
                )}
              </div>

              {isAdmin() && (
                <div className="bg-slate-900 rounded-xl p-4 border border-slate-700 space-y-3">
                  <h4 className="text-white font-semibold">Quan ly topic MQTT (admin)</h4>
                  <div className="flex flex-wrap gap-2">
                    {topics.map((t) => (
                      <span key={t} className="px-2 py-1 rounded bg-slate-800 text-slate-200 text-xs border border-slate-700">
                        {t}
                      </span>
                    ))}
                    {topics.length === 0 && <span className="text-slate-400 text-sm">Chua co topic.</span>}
                  </div>
                  <div className="flex flex-col md:flex-row gap-3">
                    <input
                      type="text"
                      value={topicInput}
                      onChange={(e) => setTopicInput(e.target.value)}
                      placeholder="devices/101/telemetry"
                      className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-white"
                    />
                    <button
                      type="button"
                      disabled={topicBusy}
                      onClick={() => {
                        const topic = topicInput.trim();
                        if (!topic) return;
                        setTopicBusy(true);
                        setTopicError('');
                        apiFetch('/api/mqtt/topics/subscribe', {
                          method: 'POST',
                          body: JSON.stringify({ topic }),
                        })
                          .then((data) => {
                            setTopics(Array.isArray(data?.topics) ? data.topics : []);
                            setTopicInput('');
                          })
                          .catch((err) => setTopicError(err?.message || 'Subscribe that bai'))
                          .finally(() => setTopicBusy(false));
                      }}
                      className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white"
                    >
                      Subscribe
                    </button>
                    <button
                      type="button"
                      disabled={topicBusy}
                      onClick={() => {
                        const topic = topicInput.trim();
                        if (!topic) return;
                        setTopicBusy(true);
                        setTopicError('');
                        apiFetch('/api/mqtt/topics/unsubscribe', {
                          method: 'POST',
                          body: JSON.stringify({ topic }),
                        })
                          .then((data) => {
                            setTopics(Array.isArray(data?.topics) ? data.topics : []);
                          })
                          .catch((err) => setTopicError(err?.message || 'Unsubscribe that bai'))
                          .finally(() => setTopicBusy(false));
                      }}
                      className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-700 text-white"
                    >
                      Unsubscribe
                    </button>
                  </div>
                  {topicError && <p className="text-red-400 text-sm">{topicError}</p>}
                </div>
              )}

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {deviceMetrics.map((metric) => {
                  const Icon = metric.icon;
                  return (
                    <div
                      key={metric.key}
                      className={`bg-slate-900 rounded-xl p-6 border border-slate-700 ${
                        fullscreenMetric === metric.key ? 'fixed inset-4 z-[80] overflow-hidden' : ''
                      }`}
                    >
                      <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center space-x-3">
                          <div className="p-2 rounded-lg" style={{ backgroundColor: `${metric.color}33` }}>
                            <Icon className="h-5 w-5" style={{ color: metric.color }} />
                          </div>
                          <div>
                            <h4 className="text-white font-semibold">{metric.title}</h4>
                            <p className="text-slate-400 text-sm">Realtime (time-series)</p>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() =>
                            setFullscreenMetric((prev) => (prev === metric.key ? null : metric.key))
                          }
                          className="p-2 rounded-lg border border-slate-600 hover:bg-slate-700 text-slate-200"
                          title={fullscreenMetric === metric.key ? 'Thu nho bieu do' : 'Phong to bieu do'}
                        >
                          {fullscreenMetric === metric.key ? (
                            <Minimize2 className="h-4 w-4" />
                          ) : (
                            <Maximize2 className="h-4 w-4" />
                          )}
                        </button>
                      </div>
                      <ResponsiveContainer width="100%" height={fullscreenMetric === metric.key ? 520 : 260}>
                        <LineChart data={realtimeSeries}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                          <XAxis dataKey="time" stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                          <YAxis stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                          <Tooltip
                            contentStyle={{
                              backgroundColor: '#1e293b',
                              border: '1px solid #334155',
                              borderRadius: '8px',
                              color: '#fff',
                            }}
                          />
                          <Legend />
                          <Line
                            type="monotone"
                            dataKey={metric.key}
                            name={metric.lineName}
                            stroke={metric.color}
                            strokeWidth={2}
                            dot={false}
                            isAnimationActive={false}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  );
                })}
              </div>
              {fullscreenMetric && (
                <div
                  className="fixed inset-0 z-[70] bg-black/70 backdrop-blur-[1px]"
                  onClick={() => setFullscreenMetric(null)}
                />
              )}
            </div>
          )}
        </div>
      </div>

      {/* Change Password Modal */}
      {showPasswordModal && (
        <ChangePasswordModal
          deviceId={device.id}
          onClose={() => setShowPasswordModal(false)}
        />
      )}
    </div>
  );
};

export default DeviceDetail;
