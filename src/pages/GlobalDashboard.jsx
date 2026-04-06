import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Activity, Gauge, Maximize2, Minimize2, Thermometer, Waves, Zap } from 'lucide-react';
import { apiFetch } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';

const WS_BASE = import.meta.env.VITE_WS_URL ?? '';

function normalizeDeviceType(type) {
  const t = String(type || '').trim().toLowerCase();
  if (t === 'temperature' || t.includes('nhiet')) return 'Temperature';
  if (t === 'power' || t.includes('cong suat')) return 'Power';
  if (t === 'vibration' || t.includes('do rung')) return 'Vibration';
  return '';
}

function inferDeviceTypeFromUpdate(update) {
  const normalized = normalizeDeviceType(update?.device_type ?? update?.type);
  if (normalized) return normalized;

  const hasVoltage = Number.isFinite(Number(update?.voltage));
  const hasCurrent = Number.isFinite(Number(update?.current));
  const hasTemperature = Number.isFinite(Number(update?.temperature));
  const hasVibration = Number.isFinite(
    Number(update?.vibration ?? update?.vibration_mms ?? update?.vibrationMmS)
  );

  if (hasVoltage || hasCurrent) return 'Power';
  if (hasTemperature) return 'Temperature';
  if (hasVibration) return 'Vibration';
  return '';
}

function toFiniteNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function normalizeDeviceRow(row) {
  const rawId = row?.device_id ?? row?.id;
  if (rawId == null) return null;
  const deviceId = String(rawId);
  return {
    deviceId,
    name: row?.devicename ?? row?.name ?? `Device ${deviceId}`,
    deviceType: normalizeDeviceType(row?.device_type ?? row?.type),
  };
}

function computeYAxisDomain(data, key) {
  const values = data
    .map((item) => Number(item[key]))
    .filter((v) => Number.isFinite(v));

  if (values.length === 0) return [0, 10];

  const min = Math.min(...values);
  const max = Math.max(...values);

  if (min === max) {
    const pad = Math.max(1, Math.abs(max) * 0.2);
    return [Math.max(0, min - pad), max + pad];
  }

  const pad = (max - min) * 0.1;
  return [Math.max(0, min - pad), max + pad];
}

function getBarSize(deviceCount) {
  if (deviceCount <= 0) return 24;
  return Math.max(10, Math.min(36, Math.floor(280 / deviceCount)));
}

function getCategoryGap(deviceCount) {
  if (deviceCount <= 4) return '24%';
  if (deviceCount <= 8) return '16%';
  if (deviceCount <= 14) return '10%';
  return '6%';
}

const chartTooltipStyle = {
  backgroundColor: '#1e293b',
  border: '1px solid #334155',
  borderRadius: '8px',
  color: '#fff',
};

function MetricBarChartCard({
  chartKey,
  title,
  subtitle,
  icon: Icon,
  iconClassName,
  data,
  dataKey,
  unit,
  color,
  isFullscreen,
  onToggleFullscreen,
}) {
  const yDomain = useMemo(() => computeYAxisDomain(data, dataKey), [data, dataKey]);
  const deviceCount = data.length;

  return (
    <div
      className={`bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-lg ${
        isFullscreen ? 'fixed inset-4 z-[80] overflow-hidden' : ''
      }`}
    >
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <div className={`p-2 rounded-lg ${iconClassName}`}>
            <Icon className="h-5 w-5" style={{ color }} />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">{title}</h3>
            <p className="text-slate-400 text-sm">{subtitle}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => onToggleFullscreen(chartKey)}
          className="p-2 rounded-lg border border-slate-600 hover:bg-slate-700 text-slate-200"
          title={isFullscreen ? 'Thu nho bieu do' : 'Phong to bieu do'}
        >
          {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
        </button>
      </div>

      <ResponsiveContainer width="100%" height={isFullscreen ? 520 : 300}>
        <BarChart
          data={data}
          margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
          barCategoryGap={getCategoryGap(deviceCount)}
          barSize={getBarSize(deviceCount)}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="deviceId"
            stroke="#94a3b8"
            tick={false}
            height={12}
          />
          <YAxis
            domain={yDomain}
            stroke="#94a3b8"
            tick={{ fill: '#94a3b8', fontSize: 12 }}
            width={46}
            allowDecimals
          />
          <Tooltip
            contentStyle={chartTooltipStyle}
            formatter={(value) => [`${toFiniteNumber(value).toFixed(2)} ${unit}`, title]}
            labelFormatter={(label, payload) => {
              const deviceName = payload?.[0]?.payload?.deviceName;
              return `Device: ${deviceName || label}`;
            }}
          />
          <Bar dataKey={dataKey} fill={color} radius={[6, 6, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function GlobalDashboard() {
  const { isAdmin } = useAuth();
  const [devices, setDevices] = useState([]);
  const [metricsByDevice, setMetricsByDevice] = useState({});
  const [loadingDevices, setLoadingDevices] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [fullscreenChart, setFullscreenChart] = useState(null);

  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);

  useEffect(() => {
    let mounted = true;

    const loadDevices = async () => {
      setLoadingDevices(true);
      setLoadError('');
      try {
        const path = isAdmin() ? '/api/devices' : '/api/devices/my';
        const list = await apiFetch(path);
        const normalized = (Array.isArray(list) ? list : [])
          .map(normalizeDeviceRow)
          .filter(Boolean);

        if (!mounted) return;
        setDevices(normalized);
        setMetricsByDevice((prev) => {
          const next = { ...prev };
          normalized.forEach((d) => {
            if (!next[d.deviceId]) {
              next[d.deviceId] = { current: 0, voltage: 0, temperature: 0, vibration: 0 };
            }
          });
          return next;
        });
      } catch (err) {
        if (!mounted) return;
        setLoadError(err?.message || 'Khong tai duoc danh sach thiet bi');
      } finally {
        if (mounted) setLoadingDevices(false);
      }
    };

    loadDevices();
    return () => {
      mounted = false;
    };
  }, [isAdmin]);

  useEffect(() => {
    const url = WS_BASE ? `${WS_BASE}/ws/global` : null;
    if (!url) return undefined;

    let closedByEffect = false;

    const connect = () => {
      if (closedByEffect) return;

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onmessage = (ev) => {
        let msg = null;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }

        const updates = Array.isArray(msg.devices)
          ? msg.devices
          : (msg.deviceId || msg.device_id || msg.id)
            ? [msg]
            : [];

        if (updates.length === 0) return;

        const discovered = [];
        const typeUpdates = [];
        setMetricsByDevice((prev) => {
          const next = { ...prev };
          updates.forEach((u) => {
            const idRaw = u.deviceId ?? u.device_id ?? u.id;
            if (idRaw == null) return;
            const deviceId = String(idRaw);
            const inferredType = inferDeviceTypeFromUpdate(u);
            typeUpdates.push({ deviceId, deviceType: inferredType });
            if (!next[deviceId]) {
              next[deviceId] = { current: 0, voltage: 0, temperature: 0, vibration: 0 };
              discovered.push(deviceId);
            }
            next[deviceId] = {
              current: toFiniteNumber(u.current, next[deviceId].current),
              voltage: toFiniteNumber(u.voltage, next[deviceId].voltage),
              temperature: toFiniteNumber(u.temperature, next[deviceId].temperature),
              vibration: toFiniteNumber(
                u.vibration ?? u.vibration_mms ?? u.vibrationMmS,
                next[deviceId].vibration
              ),
            };
          });
          return next;
        });

        if (discovered.length > 0) {
          setDevices((prev) => {
            const exists = new Set(prev.map((d) => d.deviceId));
            const added = discovered
              .filter((id) => !exists.has(id))
              .map((id) => {
                const t = typeUpdates.find((x) => x.deviceId === id)?.deviceType || '';
                return { deviceId: id, name: `Device ${id}`, deviceType: t };
              });
            return added.length ? [...prev, ...added] : prev;
          });
        }

        if (typeUpdates.length > 0) {
          setDevices((prev) =>
            prev.map((d) => {
              const latest = typeUpdates.find((x) => x.deviceId === d.deviceId);
              if (!latest?.deviceType || latest.deviceType === d.deviceType) return d;
              return { ...d, deviceType: latest.deviceType };
            })
          );
        }
      };

      ws.onclose = () => {
        if (closedByEffect) return;
        reconnectTimerRef.current = setTimeout(connect, 1200);
      };
    };

    connect();

    return () => {
      closedByEffect = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  useEffect(() => {
    if (!fullscreenChart) return undefined;
    const onKeydown = (event) => {
      if (event.key === 'Escape') setFullscreenChart(null);
    };
    window.addEventListener('keydown', onKeydown);
    return () => window.removeEventListener('keydown', onKeydown);
  }, [fullscreenChart]);

  const dashboardData = useMemo(() => {
    const idSet = new Set(devices.map((d) => d.deviceId));
    Object.keys(metricsByDevice).forEach((id) => idSet.add(id));
    return Array.from(idSet)
      .sort((a, b) => a.localeCompare(b))
      .map((deviceId) => {
        const info = devices.find((d) => d.deviceId === deviceId);
        const m = metricsByDevice[deviceId] || {
          current: 0,
          voltage: 0,
          temperature: 0,
          vibration: 0,
        };
        return {
          deviceId,
          deviceName: info?.name ?? `Device ${deviceId}`,
          deviceType: info?.deviceType ?? '',
          current: toFiniteNumber(m.current),
          voltage: toFiniteNumber(m.voltage),
          temperature: toFiniteNumber(m.temperature),
          vibration: toFiniteNumber(m.vibration),
        };
      });
  }, [devices, metricsByDevice]);

  const temperatureData = useMemo(
    () => dashboardData.filter((d) => d.deviceType === 'Temperature'),
    [dashboardData]
  );
  const powerData = useMemo(
    () => dashboardData.filter((d) => d.deviceType === 'Power'),
    [dashboardData]
  );
  const vibrationData = useMemo(
    () => dashboardData.filter((d) => d.deviceType === 'Vibration'),
    [dashboardData]
  );

  const scopeLabel = isAdmin()
    ? 'Tong quan tat ca thiet bi (admin)'
    : 'Tong quan thiet bi duoc phan quyen (user)';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Global Dashboard</h1>
          <p className="text-slate-400">{scopeLabel}</p>
        </div>
        <div className="flex items-center space-x-2 bg-slate-800 px-4 py-2 rounded-lg border border-slate-700">
          <Activity className="h-5 w-5 text-green-500 animate-pulse" />
          <span className="text-slate-300 text-sm">Live - {dashboardData.length} devices</span>
        </div>
      </div>

      {loadError && (
        <div className="p-3 rounded-lg bg-red-900/30 border border-red-700 text-red-200 text-sm">
          {loadError}
        </div>
      )}
      {!WS_BASE && (
        <div className="p-3 rounded-lg bg-amber-900/30 border border-amber-700 text-amber-200 text-sm">
          Missing <span className="font-semibold">VITE_WS_URL</span>. Dashboard chua nhan realtime.
        </div>
      )}
      {loadingDevices && (
        <div className="p-3 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 text-sm">
          Dang tai danh sach thiet bi...
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <MetricBarChartCard
          chartKey="current"
          title="Current (A)"
          subtitle="Truc X: thiet bi - Truc Y: gia tri"
          icon={Gauge}
          iconClassName="bg-blue-500/20"
          data={powerData}
          dataKey="current"
          unit="A"
          color="#3b82f6"
          isFullscreen={fullscreenChart === 'current'}
          onToggleFullscreen={(key) =>
            setFullscreenChart((prev) => (prev === key ? null : key))
          }
        />
        <MetricBarChartCard
          chartKey="voltage"
          title="Voltage (V)"
          subtitle="Truc X: thiet bi - Truc Y: gia tri"
          icon={Zap}
          iconClassName="bg-purple-500/20"
          data={powerData}
          dataKey="voltage"
          unit="V"
          color="#a855f7"
          isFullscreen={fullscreenChart === 'voltage'}
          onToggleFullscreen={(key) =>
            setFullscreenChart((prev) => (prev === key ? null : key))
          }
        />
        <MetricBarChartCard
          chartKey="temperature"
          title="Temperature (°C)"
          subtitle="Truc X: thiet bi - Truc Y: gia tri"
          icon={Thermometer}
          iconClassName="bg-red-500/20"
          data={temperatureData}
          dataKey="temperature"
          unit="°C"
          color="#ef4444"
          isFullscreen={fullscreenChart === 'temperature'}
          onToggleFullscreen={(key) =>
            setFullscreenChart((prev) => (prev === key ? null : key))
          }
        />
        <MetricBarChartCard
          chartKey="vibration"
          title="Vibration (mm/s)"
          subtitle="Truc X: thiet bi - Truc Y: gia tri"
          icon={Waves}
          iconClassName="bg-emerald-500/20"
          data={vibrationData}
          dataKey="vibration"
          unit="mm/s"
          color="#10b981"
          isFullscreen={fullscreenChart === 'vibration'}
          onToggleFullscreen={(key) =>
            setFullscreenChart((prev) => (prev === key ? null : key))
          }
        />
      </div>
      {fullscreenChart && (
        <div
          className="fixed inset-0 z-[70] bg-black/70 backdrop-blur-[1px]"
          onClick={() => setFullscreenChart(null)}
        />
      )}
    </div>
  );
}
