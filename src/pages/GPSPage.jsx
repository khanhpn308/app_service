import React, { useEffect, useState } from 'react';
import GPSDashboard from '../components/Dashboard/GPS/GPSDashboard';
import { apiFetch } from '../lib/api';

const GPSPage = () => {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchRealGpsData = async () => {
      try {
        // 1. Lấy danh sách thiết bị từ MySQL (Metadata)
        const deviceList = await apiFetch('/api/devices');
        
        // 2. Lấy dữ liệu lịch sử từ InfluxDB (60 phút gần nhất)
        const historyData = await apiFetch('/api/mqtt/history?minutes=60');
        const historyItems = historyData?.items || [];

        // 3. Gộp dữ liệu: Tìm tọa độ mới nhất cho mỗi thiết bị
        const mergedData = (deviceList || []).map(device => {
          // Tìm các bản tin của thiết bị này trong lịch sử, lấy điểm mới nhất
          // (Lưu ý: API history thường đã sắp xếp, nhưng ta lọc chắc chắn theo device_id)
          const deviceHistory = historyItems.filter(item => 
            String(item.device_id) === String(device.device_id)
          );
          
          // Lấy điểm cuối cùng trong mảng (mới nhất)
          const latestPoint = deviceHistory[deviceHistory.length - 1];

          return {
            ...device,
            // Lấy tọa độ x, y từ InfluxDB. Nếu null thì giữ null (không mock)
            x: latestPoint?.x ?? null,
            y: latestPoint?.y ?? null,
            location: latestPoint?.location || device.location || 'unknown',
            ts_iso: latestPoint?.ts_iso || null
          };
        });

        setDevices(mergedData);
      } catch (error) {
        console.error('Failed to fetch real GPS data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchRealGpsData();
    
    // Thiết lập polling để cập nhật tọa độ mỗi 15 giây
    const interval = setInterval(fetchRealGpsData, 15000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-full text-foreground bg-background rounded-xl">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
        <p>Đang đồng bộ tọa độ từ InfluxDB...</p>
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
