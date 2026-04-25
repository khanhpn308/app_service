import React, { useEffect, useMemo, useState } from 'react';
import { Send, RefreshCw, FlaskConical } from 'lucide-react';
import { apiFetch } from '../lib/api';
import { Switch } from '@/components/ui/switch';

const PROTOCOLS = ['websocket'];

function formatTime(v) {
  if (!v) return '';
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return String(v);
  return d.toLocaleString();
}

function formatMs(v) {
  if (v == null) return '-';
  return `${v} ms`;
}

export default function TestPage() {
  const [enabled, setEnabled] = useState(false);
  const [protocol, setProtocol] = useState('websocket');
  const [gatewayId, setGatewayId] = useState('');
  const [nodeId, setNodeId] = useState('');
  const [message, setMessage] = useState('');

  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');

  const loadAll = async () => {
    setError('');
    setLoading(true);
    try {
      const [cfg, logRes] = await Promise.all([
        apiFetch('/api/test/config'),
        apiFetch('/api/test/logs?limit=100'),
      ]);
      setEnabled(Boolean(cfg?.enabled));
      setProtocol(String(cfg?.protocol || 'websocket'));
      setGatewayId(String(cfg?.gateway_id || ''));
      setNodeId(String(cfg?.node_id || ''));
      setMessage(String(cfg?.message || ''));
      setLogs(Array.isArray(logRes?.items) ? logRes.items : []);
    } catch (err) {
      setError(err?.message || 'Khong tai duoc du lieu test');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const saveConfig = async (nextEnabled = enabled) => {
    setSaving(true);
    setError('');
    setOk('');
    try {
      await apiFetch('/api/test/config', {
        method: 'PUT',
        body: JSON.stringify({
          enabled: Boolean(nextEnabled),
          protocol,
          gateway_id: gatewayId.trim(),
          node_id: nodeId.trim(),
          message,
        }),
      });
      setEnabled(Boolean(nextEnabled));
      setOk('Da luu cau hinh test');
    } catch (err) {
      setError(err?.message || 'Luu cau hinh that bai');
    } finally {
      setSaving(false);
    }
  };

  const sendMessage = async () => {
    setSending(true);
    setError('');
    setOk('');
    try {
      await apiFetch('/api/test/send', {
        method: 'POST',
        body: JSON.stringify({
          protocol,
          gateway_id: gatewayId.trim(),
          node_id: nodeId.trim(),
          message,
        }),
      });
      setOk('Da gui payload test den gateway/node da chon');
    } catch (err) {
      setError(err?.message || 'Gui message that bai');
    } finally {
      setSending(false);
    }
  };

  const rows = useMemo(() => logs, [logs]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">TEST</h1>
          <p className="text-slate-400">Admin test delay node-gateway-server theo payload binary.</p>
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
      {ok && <div className="p-3 rounded-lg bg-emerald-900/30 border border-emerald-700 text-emerald-200 text-sm">{ok}</div>}

      <div className="bg-slate-800 rounded-xl border border-slate-700 p-4 space-y-4">
        <div className="flex items-center gap-2 text-white font-semibold">
          <FlaskConical className="h-4 w-4 text-cyan-400" />
          Cau hinh test
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="space-y-1">
            <span className="text-sm text-slate-300">Protocol</span>
            <select
              value={protocol}
              onChange={(e) => setProtocol(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white"
            >
              {PROTOCOLS.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </label>

          <label className="space-y-1">
            <span className="text-sm text-slate-300">Gateway ID</span>
            <input
              type="text"
              value={gatewayId}
              onChange={(e) => setGatewayId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white"
              placeholder="tempt-01"
            />
          </label>

          <label className="space-y-1">
            <span className="text-sm text-slate-300">Node ID</span>
            <input
              type="text"
              value={nodeId}
              onChange={(e) => setNodeId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white"
              placeholder="node_01"
            />
          </label>

          <label className="space-y-1">
            <span className="text-sm text-slate-300">Message</span>
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white"
              placeholder="hello from server"
            />
          </label>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="inline-flex items-center gap-3 px-3 py-2 rounded-lg bg-slate-900 border border-slate-600">
            <span className="text-sm text-slate-200">Switch</span>
            <Switch
              checked={enabled}
              disabled={saving}
              onCheckedChange={(checked) => saveConfig(checked)}
              className="data-[state=checked]:bg-emerald-500 data-[state=unchecked]:bg-slate-600"
            />
            <span className="text-sm text-slate-300">{enabled ? 'ON' : 'OFF'}</span>
          </div>

          <button
            type="button"
            onClick={() => saveConfig(enabled)}
            disabled={saving}
            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
          >
            {saving ? 'Dang luu...' : 'Luu cau hinh'}
          </button>

          <button
            type="button"
            onClick={sendMessage}
            disabled={sending || !gatewayId.trim() || !nodeId.trim() || !message.trim()}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-700 text-white disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
            {sending ? 'Dang gui...' : 'Send message'}
          </button>
        </div>
      </div>

      <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-700 text-slate-300 text-sm">Logs</div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-slate-900 border-b border-slate-700">
                <th className="px-4 py-3 text-left text-slate-300 text-sm">Protocol</th>
                <th className="px-4 py-3 text-left text-slate-300 text-sm">Delay node to gateway</th>
                <th className="px-4 py-3 text-left text-slate-300 text-sm">Delay gateway to server</th>
                <th className="px-4 py-3 text-left text-slate-300 text-sm">Delay node to server</th>
                <th className="px-4 py-3 text-left text-slate-300 text-sm">Time test</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {loading ? (
                <tr>
                  <td className="px-4 py-4 text-slate-400" colSpan={5}>Dang tai...</td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td className="px-4 py-4 text-slate-400" colSpan={5}>Chua co log test</td>
                </tr>
              ) : (
                rows.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-900/40">
                    <td className="px-4 py-3 text-slate-100">{r.protocol}</td>
                    <td className="px-4 py-3 text-cyan-300">{formatMs(r.delay_node_to_gateway_ms)}</td>
                    <td className="px-4 py-3 text-emerald-300">{formatMs(r.delay_gateway_to_server_ms)}</td>
                    <td className="px-4 py-3 text-blue-300">{formatMs(r.delay_node_to_server_ms)}</td>
                    <td className="px-4 py-3 text-slate-200">{formatTime(r.time_test)}</td>
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
