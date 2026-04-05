import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Activity, Gauge, Thermometer, Waves } from 'lucide-react';
import { mockDevices } from '../data/mockData';

const WS_BASE = import.meta.env.VITE_WS_URL ?? '';

function formatTime(ts) {
  try {
    return new Date(ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return String(ts);
  }
}

function capPush(arr, item, max = 60) {
  const next = [...arr, item];
  return next.length > max ? next.slice(next.length - max) : next;
}

export default function GlobalDashboard() {
  const devices = useMemo(() => mockDevices, []);

  const [currentSeries, setCurrentSeries] = useState([]); // multi-line: one line per device
  const [temperatureSeries, setTemperatureSeries] = useState([]); // multi-line: one line per device
  const [vibrationBars, setVibrationBars] = useState(() =>
    devices.map((d) => ({ deviceId: d.id, vibration: 0 }))
  ); // bar: one bar per device

  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);

  useEffect(() => {
    // WebSocket init (Global dashboard)
    // Expect payload examples:
    // - { ts, deviceId, current, temperature, vibration }
    // - { ts, devices: [{ deviceId, current, temperature, vibration }, ...] }
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

        const ts = msg.ts ?? Date.now();
        const time = formatTime(ts);
        const updates = Array.isArray(msg.devices)
          ? msg.devices
          : msg.deviceId
            ? [msg]
            : [];

        if (updates.length === 0) return;

        setCurrentSeries((prev) => {
          const row = { time };
          updates.forEach((u) => {
            if (!u.deviceId) return;
            row[u.deviceId] = typeof u.current === 'number' ? u.current : Number(u.current);
          });
          return capPush(prev, row);
        });

        setTemperatureSeries((prev) => {
          const row = { time };
          updates.forEach((u) => {
            if (!u.deviceId) return;
            row[u.deviceId] = typeof u.temperature === 'number' ? u.temperature : Number(u.temperature);
          });
          return capPush(prev, row);
        });

        setVibrationBars((prev) => {
          const map = new Map(prev.map((x) => [x.deviceId, x]));
          updates.forEach((u) => {
            if (!u.deviceId) return;
            const vibration = typeof u.vibration === 'number' ? u.vibration : Number(u.vibration);
            map.set(u.deviceId, { deviceId: u.deviceId, vibration: Number.isFinite(vibration) ? vibration : 0 });
          });
          return Array.from(map.values()).sort((a, b) => a.deviceId.localeCompare(b.deviceId));
        });
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
  }, []);

  const deviceColors = useMemo(() => {
    const palette = ['#3b82f6', '#ef4444', '#22c55e', '#a855f7', '#f59e0b', '#06b6d4', '#e11d48'];
    const map = {};
    devices.forEach((d, idx) => {
      map[d.id] = palette[idx % palette.length];
    });
    return map;
  }, [devices]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Global Dashboard</h1>
          <p className="text-slate-400">Biểu đồ tổng hợp toàn hệ thống (real-time)</p>
        </div>
        <div className="flex items-center space-x-2 bg-slate-800 px-4 py-2 rounded-lg border border-slate-700">
          <Activity className="h-5 w-5 text-green-500 animate-pulse" />
          <span className="text-slate-300 text-sm">Live</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Current - Line chart (multi-device) */}
        <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-lg">
          <div className="flex items-center space-x-3 mb-6">
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <Gauge className="h-5 w-5 text-blue-500" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">Current (A)</h3>
              <p className="text-slate-400 text-sm">Tất cả thiết bị</p>
            </div>
          </div>

          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={currentSeries}>
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
              {devices.map((d) => (
                <Line
                  key={d.id}
                  type="monotone"
                  dataKey={d.id}
                  name={d.id}
                  stroke={deviceColors[d.id]}
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Temperature - Line chart (multi-device) */}
        <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-lg">
          <div className="flex items-center space-x-3 mb-6">
            <div className="p-2 bg-red-500/20 rounded-lg">
              <Thermometer className="h-5 w-5 text-red-500" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">Temperature (°C)</h3>
              <p className="text-slate-400 text-sm">Tất cả thiết bị</p>
            </div>
          </div>

          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={temperatureSeries}>
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
              {devices.map((d) => (
                <Line
                  key={d.id}
                  type="monotone"
                  dataKey={d.id}
                  name={d.id}
                  stroke={deviceColors[d.id]}
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Vibration - Bar chart (per device) */}
      <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-lg">
        <div className="flex items-center space-x-3 mb-6">
          <div className="p-2 bg-emerald-500/20 rounded-lg">
            <Waves className="h-5 w-5 text-emerald-500" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">Vibration</h3>
            <p className="text-slate-400 text-sm">Biểu đồ theo thiết bị</p>
          </div>
        </div>

        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={vibrationBars}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="deviceId" stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 12 }} />
            <YAxis stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 12 }} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                borderRadius: '8px',
                color: '#fff',
              }}
            />
            <Bar dataKey="vibration" fill="#10b981" radius={[6, 6, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

