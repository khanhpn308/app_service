import React, { useEffect, useRef, useState } from 'react';
import GPSDashboard from '../components/Dashboard/GPS/GPSDashboard';
import { apiFetch } from '../lib/api';
import { openWebSocket } from '../lib/wsUrl';
import { mergeDeviceCatalog, mergeGpsMessage } from './gpsRealtime';

function resolveWsBase() {
  const envBase = String(import.meta.env.VITE_WS_URL ?? '').trim();
  return envBase ? envBase.replace(/\/$/, '') : undefined;
}

const GPSPage = () => {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);

  useEffect(() => {
    let mounted = true;

    const fetchDeviceCatalog = async () => {
      try {
        const deviceList = await apiFetch('/api/devices');
        if (!mounted) return;
        setDevices((liveDevices) => mergeDeviceCatalog(liveDevices, deviceList || []));
      } catch (error) {
        console.error('Failed to fetch device catalog:', error);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    fetchDeviceCatalog();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let closedByEffect = false;
    const connect = () => {
      if (closedByEffect) return;

      const websocket = openWebSocket('/ws/global', resolveWsBase());
      wsRef.current = websocket;

      websocket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          setDevices((currentDevices) => mergeGpsMessage(currentDevices, message));
          setLoading(false);
        } catch {
          // Kênh global chỉ sử dụng telemetry JSON.
        }
      };

      websocket.onclose = () => {
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

  if (loading) return (
    <div className="flex items-center justify-center h-full text-foreground bg-background rounded-xl">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
        <p>Đang kết nối dữ liệu GPS realtime...</p>
      </div>
    </div>
  );

  return (
    <div className="h-[calc(100vh-120px)] bg-white rounded-xl shadow-xl overflow-hidden">
      <GPSDashboard initialDevices={devices} />
    </div>
  );
};

export default GPSPage;
