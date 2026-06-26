import React, { useMemo } from 'react';
import { Activity, AlertTriangle, Cpu, Wifi, WifiOff } from 'lucide-react';
import { deviceStatsSummary, mockDevices, mockRecentAlerts } from '../data/mockData';
import { PageHeader } from '../components/common/PageHeader';
import { StatCard } from '../components/common/StatCard';
import { Panel } from '../components/common/Panel';
import { toUiStatus } from '../lib/deviceStatus';

export default function Home() {
  const alerts = useMemo(() => mockRecentAlerts(), []);

  const statusLabel = (status) => (toUiStatus(status) === 'online' ? 'Online' : 'Offline');

  return (
    <div className="space-y-6">
      <PageHeader
        title="Home"
        description="Overview / tình trạng tổng quan hệ thống"
        actions={
          <div className="flex items-center space-x-2 bg-card px-4 py-2 rounded-lg border border-border">
            <Activity className="h-5 w-5 text-green-500 animate-pulse" />
            <span className="text-muted-foreground text-sm">System Active</span>
          </div>
        }
      />

      {/* Demo data notice — trang này chưa kết nối API thật (backend chưa có endpoint summary/alerts). */}
      <div className="p-3 rounded-lg bg-amber-900/30 border border-amber-700 text-amber-200 text-sm">
        Dữ liệu trên trang này là <strong>demo</strong> (chưa kết nối API thật).
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
      <Panel className="overflow-hidden">
        <div className="px-6 py-5 border-b border-border flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-foreground">Latest Alerts / Events</h2>
            <p className="text-muted-foreground text-sm">Các cảnh báo/lỗi mới nhất</p>
          </div>
          <span className="text-muted-foreground text-sm">{alerts.length} items</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-muted/40 border-b border-border">
                <th className="px-6 py-4 text-left text-sm font-semibold text-muted-foreground">Time</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-muted-foreground">Device</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-muted-foreground">Severity</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-muted-foreground">Message</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-muted-foreground">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {alerts.map((a) => {
                const sevColor =
                  a.severity === 'critical'
                    ? 'text-red-400'
                    : a.severity === 'warning'
                      ? 'text-amber-400'
                      : 'text-muted-foreground';
                const device = mockDevices.find((d) => d.id === a.deviceId);
                return (
                  <tr key={a.id} className="hover:bg-muted/50 transition-colors duration-150">
                    <td className="px-6 py-4 text-muted-foreground text-sm whitespace-nowrap">{a.time}</td>
                    <td className="px-6 py-4 text-foreground font-medium whitespace-nowrap">{a.deviceId}</td>
                    <td className={`px-6 py-4 text-sm font-semibold ${sevColor}`}>{a.severity.toUpperCase()}</td>
                    <td className="px-6 py-4 text-foreground/90 text-sm">{a.message}</td>
                    <td className="px-6 py-4 text-muted-foreground text-sm whitespace-nowrap">
                      {device ? statusLabel(device.status) : '-'}
                    </td>
                  </tr>
                );
              })}
              {alerts.length === 0 && (
                <tr>
                  <td className="px-6 py-10 text-center text-muted-foreground" colSpan={5}>
                    No alerts/events.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
