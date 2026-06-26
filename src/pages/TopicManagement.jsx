import React, { useEffect, useMemo, useState } from 'react';
import { RefreshCw, Save, RadioTower } from 'lucide-react';
import { apiFetch } from '../lib/api';

function normalizeDevices(rows) {
  return (Array.isArray(rows) ? rows : []).map((d) => ({
    device_id: d.device_id,
    devicename: d.devicename || `Device ${d.device_id}`,
    status: d.status || 'deactive',
    topic: d.topic || '',
    publish_topic: d.publish_topic || '',
  }));
}

export default function TopicManagement() {
  const [devices, setDevices] = useState([]);
  const [topicMap, setTopicMap] = useState({});
  const [publishTopicMap, setPublishTopicMap] = useState({});
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
      const nextPublishMap = {};
      normalized.forEach((d) => {
        nextMap[d.device_id] = d.topic || '';
        nextPublishMap[d.device_id] = d.publish_topic || '';
      });
      setTopicMap(nextMap);
      setPublishTopicMap(nextPublishMap);
    } catch (err) {
      setError(err?.message || 'Không tải được dữ liệu topic');
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
      const publishTopic = String(publishTopicMap[deviceId] || '').trim();
      await apiFetch(`/api/devices/${encodeURIComponent(deviceId)}/topic`, {
        method: 'PUT',
        body: JSON.stringify({
          topic: topic || null,
          publish_topic: publishTopic || null,
        }),
      });
      setOkMsg(`Đã lưu topic nhận/gửi cho device ${deviceId}`);
      await loadAll();
    } catch (err) {
      setError(err?.message || 'Lưu topic thất bại');
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2">Quản lý topic MQTT</h1>
          <p className="text-muted-foreground">Admin lưu topic trên bảng device và backend sẽ tự động subscribe.</p>
        </div>
        <button
          type="button"
          onClick={loadAll}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-card border border-border text-foreground/90 hover:bg-muted"
        >
          <RefreshCw className="h-4 w-4" />
          Làm mới
        </button>
      </div>

      {error && <div className="p-3 rounded-lg bg-red-900/30 border border-red-700 text-red-200 text-sm">{error}</div>}
      {okMsg && <div className="p-3 rounded-lg bg-emerald-900/30 border border-emerald-700 text-emerald-200 text-sm">{okMsg}</div>}

      <div className="bg-card rounded-xl border border-border p-4">
        <div className="flex items-center gap-2 mb-3">
          <RadioTower className="h-4 w-4 text-cyan-400" />
          <h2 className="text-foreground font-semibold">Topic runtime đang subscribe</h2>
        </div>
        {sortedRuntimeTopics.length === 0 ? (
          <p className="text-muted-foreground text-sm">Chưa có topic nào.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {sortedRuntimeTopics.map((t) => (
              <span key={t} className="px-2 py-1 rounded bg-background border border-border text-foreground/90 text-xs">
                {t}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="bg-card rounded-xl border border-border overflow-hidden">
        <div className="px-4 py-3 border-b border-border text-foreground/90 text-sm">
          Gán topic nhận/topic gửi theo từng thiết bị (bỏ trống để xoá giá trị).
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-background border-b border-border">
                <th className="px-4 py-3 text-left text-foreground/90 text-sm">Device ID</th>
                <th className="px-4 py-3 text-left text-foreground/90 text-sm">Tên thiết bị</th>
                <th className="px-4 py-3 text-left text-foreground/90 text-sm">Trạng thái</th>
                <th className="px-4 py-3 text-left text-foreground/90 text-sm">Topic nhan (subscribe)</th>
                <th className="px-4 py-3 text-left text-foreground/90 text-sm">Topic gui (publish)</th>
                <th className="px-4 py-3 text-left text-foreground/90 text-sm">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading ? (
                <tr>
                  <td className="px-4 py-4 text-muted-foreground" colSpan={6}>Đang tải...</td>
                </tr>
              ) : (
                devices.map((d) => (
                  <tr key={d.device_id} className="hover:bg-background/40">
                    <td className="px-4 py-3 text-primary font-mono">{d.device_id}</td>
                    <td className="px-4 py-3 text-foreground">{d.devicename}</td>
                    <td className="px-4 py-3 text-foreground/90">{d.status}</td>
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
                        className="w-full px-3 py-2 rounded-lg bg-background border border-border text-foreground"
                      />
                    </td>
                    <td className="px-4 py-3 min-w-[320px]">
                      <input
                        type="text"
                        value={publishTopicMap[d.device_id] ?? ''}
                        onChange={(e) =>
                          setPublishTopicMap((prev) => ({
                            ...prev,
                            [d.device_id]: e.target.value,
                          }))
                        }
                        placeholder="devices/101/downlink"
                        className="w-full px-3 py-2 rounded-lg bg-background border border-border text-foreground"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        disabled={savingId === d.device_id}
                        onClick={() => saveTopic(d.device_id)}
                        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-primary hover:bg-primary/90 text-foreground disabled:opacity-50"
                      >
                        <Save className="h-4 w-4" />
                        {savingId === d.device_id ? 'Đang lưu...' : 'Lưu'}
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
