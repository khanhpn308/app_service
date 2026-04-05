import React, { useMemo } from 'react';
import { Activity, AlertTriangle, Cpu, Wifi, WifiOff } from 'lucide-react';
import { deviceStatsSummary, mockDevices, mockRecentAlerts } from '../data/mockData';

export default function Home() {
  const alerts = useMemo(() => mockRecentAlerts(), []);

  const StatCard = ({ title, value, icon: Icon, color, subtitle }) => (
    <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-lg hover:shadow-xl transition-all duration-200">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-slate-400 text-sm font-medium mb-2">{title}</p>
          <p className={`text-3xl font-bold ${color}`}>{value}</p>
          {subtitle && <p className="text-slate-500 text-xs mt-2">{subtitle}</p>}
        </div>
        <div className={`p-3 rounded-lg ${color.replace('text', 'bg').replace('500', '500/20')}`}>
          <Icon className={`h-6 w-6 ${color}`} />
        </div>
      </div>
    </div>
  );

  const statusLabel = (status) => (status === 'online' ? 'Online' : 'Offline');

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Home</h1>
          <p className="text-slate-400">Overview / tình trạng tổng quan hệ thống</p>
        </div>
        <div className="flex items-center space-x-2 bg-slate-800 px-4 py-2 rounded-lg border border-slate-700">
          <Activity className="h-5 w-5 text-green-500 animate-pulse" />
          <span className="text-slate-300 text-sm">System Active</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Devices"
          value={deviceStatsSummary.total}
          icon={Cpu}
          color="text-blue-500"
          subtitle="Thiết bị đã khai báo"
        />
        <StatCard
          title="Online"
          value={deviceStatsSummary.online}
          icon={Wifi}
          color="text-green-500"
          subtitle="Kết nối bình thường"
        />
        <StatCard
          title="Offline"
          value={deviceStatsSummary.offline}
          icon={WifiOff}
          color="text-red-500"
          subtitle="Mất kết nối"
        />
        <StatCard
          title="Active Alerts"
          value={alerts.filter((a) => a.severity !== 'info').length}
          icon={AlertTriangle}
          color="text-amber-500"
          subtitle="Cảnh báo gần nhất"
        />
      </div>

      {/* Latest Alerts / Events */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden shadow-lg">
        <div className="px-6 py-5 border-b border-slate-700 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white">Latest Alerts / Events</h2>
            <p className="text-slate-400 text-sm">Các cảnh báo/lỗi mới nhất</p>
          </div>
          <span className="text-slate-400 text-sm">{alerts.length} items</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-slate-900 border-b border-slate-700">
                <th className="px-6 py-4 text-left text-sm font-semibold text-slate-300">Time</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-slate-300">Device</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-slate-300">Severity</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-slate-300">Message</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-slate-300">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {alerts.map((a) => {
                const sevColor =
                  a.severity === 'critical'
                    ? 'text-red-400'
                    : a.severity === 'warning'
                      ? 'text-amber-400'
                      : 'text-slate-300';
                const device = mockDevices.find((d) => d.id === a.deviceId);
                return (
                  <tr key={a.id} className="hover:bg-slate-900 transition-colors duration-150">
                    <td className="px-6 py-4 text-slate-400 text-sm whitespace-nowrap">{a.time}</td>
                    <td className="px-6 py-4 text-white font-medium whitespace-nowrap">{a.deviceId}</td>
                    <td className={`px-6 py-4 text-sm font-semibold ${sevColor}`}>{a.severity.toUpperCase()}</td>
                    <td className="px-6 py-4 text-slate-200 text-sm">{a.message}</td>
                    <td className="px-6 py-4 text-slate-400 text-sm whitespace-nowrap">
                      {device ? statusLabel(device.status) : '-'}
                    </td>
                  </tr>
                );
              })}
              {alerts.length === 0 && (
                <tr>
                  <td className="px-6 py-10 text-center text-slate-400" colSpan={5}>
                    No alerts/events.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

