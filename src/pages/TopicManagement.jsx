import React, { useEffect, useMemo, useState } from 'react';
import { RefreshCw, Save, RadioTower } from 'lucide-react';
import { apiFetch } from '../lib/api';

function normalizeDevices(rows) {
  return (Array.isArray(rows) ? rows : []).map((d) => ({
    device_id: d.device_id,
    devicename: d.devicename || `Device ${d.device_id}`,
    status: d.status || 'deactive',
    topic: d.topic || '',
  }));
}

export default function TopicManagement() {
  const [devices, setDevices] = useState([]);
  const [topicMap, setTopicMap] = useState({});
  const [runtimeTopics, setRuntimeTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState(null);
  const [error, setError] = useState('');
  const [okMsg, setOkMsg] = useState('');

  const loadAll = async () => {
    setError('');
    setOkMsg('');
    setLoading(true);
    try {
      const [deviceRows, mqttTopics] = await Promise.all([
        apiFetch('/api/devices/topics'),
        apiFetch('/api/mqtt/topics'),
      ]);
      const normalized = normalizeDevices(deviceRows);
      setDevices(normalized);
      setRuntimeTopics(Array.isArray(mqttTopics?.items) ? mqttTopics.items : []);

      const nextMap = {};
      normalized.forEach((d) => {
        nextMap[d.device_id] = d.topic || '';
      });
      setTopicMap(nextMap);
    } catch (err) {
      setError(err?.message || 'Khong tai duoc du lieu topic');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const sortedRuntimeTopics = useMemo(() => {
    return [...runtimeTopics].sort((a, b) => String(a).localeCompare(String(b)));
  }, [runtimeTopics]);

  const saveTopic = async (deviceId) => {
    setSavingId(deviceId);
    setError('');
    setOkMsg('');
    try {
      const topic = String(topicMap[deviceId] || '').trim();
      await apiFetch(`/api/devices/${encodeURIComponent(deviceId)}/topic`, {
        method: 'PUT',
        body: JSON.stringify({ topic: topic || null }),
      });
      setOkMsg(`Da luu topic cho device ${deviceId}`);
      await loadAll();
    } catch (err) {
      setError(err?.message || 'Luu topic that bai');
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Quan ly topic MQTT</h1>
          <p className="text-slate-400">Admin luu topic tren bang device va backend se auto subscribe.</p>
        </div>
        <button
          type="button"
          onClick={loadAll}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 hover:bg-slate-700"
        >
          <RefreshCw className="h-4 w-4" />
          Lam moi
        </button>
      </div>

      {error && <div className="p-3 rounded-lg bg-red-900/30 border border-red-700 text-red-200 text-sm">{error}</div>}
      {okMsg && <div className="p-3 rounded-lg bg-emerald-900/30 border border-emerald-700 text-emerald-200 text-sm">{okMsg}</div>}

      <div className="bg-slate-800 rounded-xl border border-slate-700 p-4">
        <div className="flex items-center gap-2 mb-3">
          <RadioTower className="h-4 w-4 text-cyan-400" />
          <h2 className="text-white font-semibold">Topic runtime dang subscribe</h2>
        </div>
        {sortedRuntimeTopics.length === 0 ? (
          <p className="text-slate-400 text-sm">Chua co topic nao.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {sortedRuntimeTopics.map((t) => (
              <span key={t} className="px-2 py-1 rounded bg-slate-900 border border-slate-700 text-slate-200 text-xs">
                {t}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-700 text-slate-300 text-sm">
          Gan topic theo tung thiet bi (bo trong de bo subscribe).
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-slate-900 border-b border-slate-700">
                <th className="px-4 py-3 text-left text-slate-300 text-sm">Device ID</th>
                <th className="px-4 py-3 text-left text-slate-300 text-sm">Ten thiet bi</th>
                <th className="px-4 py-3 text-left text-slate-300 text-sm">Trang thai</th>
                <th className="px-4 py-3 text-left text-slate-300 text-sm">Topic</th>
                <th className="px-4 py-3 text-left text-slate-300 text-sm">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {loading ? (
                <tr>
                  <td className="px-4 py-4 text-slate-400" colSpan={5}>Dang tai...</td>
                </tr>
              ) : (
                devices.map((d) => (
                  <tr key={d.device_id} className="hover:bg-slate-900/40">
                    <td className="px-4 py-3 text-blue-400 font-mono">{d.device_id}</td>
                    <td className="px-4 py-3 text-white">{d.devicename}</td>
                    <td className="px-4 py-3 text-slate-300">{d.status}</td>
                    <td className="px-4 py-3 min-w-[320px]">
                      <input
                        type="text"
                        value={topicMap[d.device_id] ?? ''}
                        onChange={(e) =>
                          setTopicMap((prev) => ({
                            ...prev,
                            [d.device_id]: e.target.value,
                          }))
                        }
                        placeholder="devices/101/telemetry"
                        className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        disabled={savingId === d.device_id}
                        onClick={() => saveTopic(d.device_id)}
                        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
                      >
                        <Save className="h-4 w-4" />
                        {savingId === d.device_id ? 'Dang luu...' : 'Luu'}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
