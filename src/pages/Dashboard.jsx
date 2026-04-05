import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, Thermometer, Droplets, Wifi, WifiOff, TrendingUp } from 'lucide-react';
import { generateTemperatureData, generateHumidityData, deviceStatsSummary, mockDevices } from '../data/mockData';

const Dashboard = () => {
  const temperatureData = generateTemperatureData();
  const humidityData = generateHumidityData();

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

  const DeviceStatusCard = ({ device }) => (
    <div className="bg-slate-800 rounded-lg p-4 border border-slate-700 hover:border-blue-500 transition-all duration-200">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <h4 className="text-white font-semibold text-sm mb-1">{device.name}</h4>
          <p className="text-slate-400 text-xs">{device.location}</p>
        </div>
        {device.status === 'online' ? (
          <Wifi className="h-5 w-5 text-green-500" />
        ) : (
          <WifiOff className="h-5 w-5 text-red-500" />
        )}
      </div>
      
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${device.status === 'online' ? 'bg-green-500' : 'bg-red-500'} animate-pulse`}></div>
          <span className={`text-xs font-medium ${device.status === 'online' ? 'text-green-500' : 'text-red-500'}`}>
            {device.status.toUpperCase()}
          </span>
        </div>
        
        <div className="text-right">
          <p className="text-white font-bold text-lg">{device.value}</p>
          <p className="text-slate-400 text-xs">{device.unit}</p>
        </div>
      </div>
      
      <div className="mt-3 pt-3 border-t border-slate-700">
        <p className="text-slate-500 text-xs">Last update: {device.lastUpdate}</p>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Dashboard</h1>
          <p className="text-slate-400">Real-time monitoring and analytics</p>
        </div>
        <div className="flex items-center space-x-2 bg-slate-800 px-4 py-2 rounded-lg border border-slate-700">
          <Activity className="h-5 w-5 text-green-500 animate-pulse" />
          <span className="text-slate-300 text-sm">System Active</span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Devices"
          value={deviceStatsSummary.total}
          icon={Activity}
          color="text-blue-500"
          subtitle="Connected devices"
        />
        <StatCard
          title="Online"
          value={deviceStatsSummary.online}
          icon={Wifi}
          color="text-green-500"
          subtitle="Active connections"
        />
        <StatCard
          title="Offline"
          value={deviceStatsSummary.offline}
          icon={WifiOff}
          color="text-red-500"
          subtitle="Inactive devices"
        />
        <StatCard
          title="Uptime"
          value={deviceStatsSummary.uptime}
          icon={TrendingUp}
          color="text-emerald-500"
          subtitle="Last 30 days"
        />
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Temperature Chart */}
        <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-lg">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-red-500/20 rounded-lg">
                <Thermometer className="h-5 w-5 text-red-500" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white">Temperature</h3>
                <p className="text-slate-400 text-sm">Last 24 hours</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-2xl font-bold text-red-500">
                {temperatureData[temperatureData.length - 1].value.toFixed(1)}°C
              </p>
              <p className="text-slate-500 text-xs">Current</p>
            </div>
          </div>
          
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={temperatureData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis 
                dataKey="time" 
                stroke="#94a3b8"
                tick={{ fill: '#94a3b8', fontSize: 12 }}
                interval="preserveStartEnd"
              />
              <YAxis 
                stroke="#94a3b8"
                tick={{ fill: '#94a3b8', fontSize: 12 }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                  color: '#fff'
                }}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#ef4444"
                strokeWidth={2}
                dot={{ fill: '#ef4444', r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Humidity Chart */}
        <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-lg">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-blue-500/20 rounded-lg">
                <Droplets className="h-5 w-5 text-blue-500" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white">Humidity</h3>
                <p className="text-slate-400 text-sm">Last 24 hours</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-2xl font-bold text-blue-500">
                {humidityData[humidityData.length - 1].value.toFixed(1)}%
              </p>
              <p className="text-slate-500 text-xs">Current</p>
            </div>
          </div>
          
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={humidityData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis 
                dataKey="time" 
                stroke="#94a3b8"
                tick={{ fill: '#94a3b8', fontSize: 12 }}
                interval="preserveStartEnd"
              />
              <YAxis 
                stroke="#94a3b8"
                tick={{ fill: '#94a3b8', fontSize: 12 }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                  color: '#fff'
                }}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={{ fill: '#3b82f6', r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Device Status Grid */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-white">Device Status Overview</h2>
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-green-500 rounded-full"></div>
              <span className="text-slate-400 text-sm">Online</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-red-500 rounded-full"></div>
              <span className="text-slate-400 text-sm">Offline</span>
            </div>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {mockDevices.map(device => (
            <DeviceStatusCard key={device.id} device={device} />
          ))}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
