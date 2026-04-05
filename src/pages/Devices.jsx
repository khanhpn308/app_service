import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Cpu, MapPin, Clock, ExternalLink, Plus, Search } from 'lucide-react';
import { apiFetch } from '../lib/api';
import { mockDevices } from '../data/mockData';
import AddDeviceModal from '../components/AddDeviceModal';

const Devices = () => {
  const navigate = useNavigate();
  const { isAdmin, user } = useAuth();
  const [devices, setDevices] = useState(mockDevices);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      setLoadError('');
      try {
        const path = isAdmin() ? '/api/devices' : '/api/devices/my';
        const list = await apiFetch(path);
        if (!mounted) return;
        setDevices(Array.isArray(list) ? list : []);
      } catch (e) {
        if (!mounted) return;
        // fallback to mock for UI continuity
        setLoadError(e.message || 'Không tải được danh sách thiết bị');
        setDevices(mockDevices);
      } finally {
        if (!mounted) return;
        setLoading(false);
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, [isAdmin]);

  const handleToggleStatus = (deviceId) => {
    setDevices(devices.map(device => 
      String(device.id ?? device.device_id) === String(deviceId)
        ? { ...device, status: device.status === 'online' ? 'offline' : 'online' }
        : device
    ));
  };

  const handleDeviceClick = (deviceId) => {
    navigate(`/devices/${deviceId}`);
  };

  const handleAddDevice = (newDevice) => {
    // Optimistically append created device; next page refresh will sync from API.
    setDevices((prev) => [...prev, newDevice]);
    setShowAddModal(false);
  };

  const normalizedDevices = useMemo(() => {
    // Normalize data shape between mock and API:
    // - mock uses { id, name, type, location, ... }
    // - DB schema uses { device_id, devicename, status }
    return devices.map((d) => {
      const id = d.id ?? d.device_id;
      const name = d.name ?? d.devicename ?? `Device ${id}`;
      const type = d.type ?? 'Motor';
      const location = d.location ?? '—';
      const lastUpdate = d.lastUpdate ?? '—';
      const value = d.value ?? '—';
      const unit = d.unit ?? '';
      return { ...d, id: String(id), name, type, location, lastUpdate, value, unit };
    });
  }, [devices]);

  const filteredDevices = normalizedDevices.filter((device) => {
    const q = searchTerm.toLowerCase();
    return (
      device.name.toLowerCase().includes(q) ||
      device.id.toLowerCase().includes(q) ||
      device.location.toLowerCase().includes(q)
    );
  });

  const DeviceCard = ({ device }) => (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden shadow-lg hover:shadow-xl hover:border-blue-500 transition-all duration-200 group">
      {/* Card Header */}
      <div className="p-6 pb-4">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-lg ${
              device.status === 'online' ? 'bg-green-500/20' : 'bg-red-500/20'
            }`}>
              <Cpu className={`h-6 w-6 ${
                device.status === 'online' ? 'text-green-500' : 'text-red-500'
              }`} />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white group-hover:text-blue-400 transition-colors">
                {device.name}
              </h3>
              <p className="text-slate-400 text-sm">{device.type}</p>
            </div>
          </div>
          
          <Link
            to={`/devices/${device.id}`}
            className="p-2 hover:bg-slate-700 rounded-lg transition-colors duration-200"
            title="View Detail"
            aria-label={`View detail ${device.id}`}
          >
            <ExternalLink className="h-5 w-5 text-slate-400 hover:text-blue-400" />
          </Link>
        </div>

        {/* Device ID */}
        <div className="bg-slate-900 rounded-lg p-3 mb-4">
          <p className="text-slate-500 text-xs mb-1">Device ID</p>
          <p className="text-blue-400 font-mono text-sm font-semibold">{device.id}</p>
        </div>

        {/* Location */}
        <div className="flex items-center space-x-2 text-slate-400 mb-3">
          <MapPin className="h-4 w-4" />
          <span className="text-sm">{device.location}</span>
        </div>

        {/* Last Update */}
        <div className="flex items-center space-x-2 text-slate-500 mb-4">
          <Clock className="h-4 w-4" />
          <span className="text-xs">{device.lastUpdate}</span>
        </div>

        {/* Current Value */}
        <div className="bg-slate-900 rounded-lg p-3 mb-4">
          <p className="text-slate-500 text-xs mb-1">Current Reading</p>
          <p className="text-white font-bold text-2xl">
            {device.value} <span className="text-slate-400 text-base">{device.unit}</span>
          </p>
        </div>
      </div>

      {/* Card Footer */}
      <div className="px-6 py-4 bg-slate-900 border-t border-slate-700 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${
            device.status === 'online' ? 'bg-green-500 animate-pulse' : 'bg-red-500'
          }`}></div>
          <span className={`text-sm font-medium ${
            device.status === 'online' ? 'text-green-500' : 'text-red-500'
          }`}>
            {device.status.toUpperCase()}
          </span>
        </div>

        {/* Live Status Toggle */}
        <button
          onClick={() => handleToggleStatus(device.id)}
          className={`px-4 py-2 rounded-lg font-medium text-sm transition-all duration-200 ${
            device.status === 'online'
              ? 'bg-red-600 hover:bg-red-700 text-white'
              : 'bg-green-600 hover:bg-green-700 text-white'
          }`}
        >
          {device.status === 'online' ? 'Turn Off' : 'Turn On'}
        </button>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Devices</h1>
          <p className="text-slate-400">Manage and monitor your IoT devices</p>
        </div>
        
        <div className="flex items-center space-x-3">
          <span className="text-slate-400">
            Total: <span className="text-white font-bold">{normalizedDevices.length}</span>
          </span>
        </div>
      </div>

      {loadError && (
        <div className="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-200 text-sm">{loadError}</div>
      )}

      {/* Search Bar */}
      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
          <Search className="h-5 w-5 text-slate-400" />
        </div>
        <input
          type="text"
          placeholder="Search devices by name, ID, or location..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-11 pr-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
        />
      </div>

      {/* Devices Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredDevices.map(device => (
          <DeviceCard key={device.id} device={device} />
        ))}
      </div>

      {/* No Results */}
      {filteredDevices.length === 0 && (
        <div className="text-center py-12">
          <Cpu className="h-16 w-16 text-slate-600 mx-auto mb-4" />
          <p className="text-slate-400 text-lg">No devices found</p>
          <p className="text-slate-500 text-sm">
            {loading
              ? 'Đang tải...'
              : isAdmin()
                ? 'Try adjusting your search criteria'
                : 'Bạn chưa được cấp quyền truy cập thiết bị nào (RBAC)'}
          </p>
        </div>
      )}

      {/* Floating Action Button - Admin Only */}
      {isAdmin() && (
        <button
          onClick={() => setShowAddModal(true)}
          className="fixed bottom-8 right-8 w-14 h-14 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-2xl shadow-blue-500/50 hover:shadow-blue-500/70 transition-all duration-200 flex items-center justify-center group hover:scale-110 z-40"
          title="Add New Device"
        >
          <Plus className="h-7 w-7" />
        </button>
      )}

      {/* Add Device Modal */}
      {showAddModal && (
        <AddDeviceModal
          onClose={() => setShowAddModal(false)}
          onAdd={handleAddDevice}
        />
      )}
    </div>
  );
};

export default Devices;
