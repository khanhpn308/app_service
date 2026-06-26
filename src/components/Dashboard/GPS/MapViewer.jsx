import React from 'react';

/**
 * MapViewer - Hiển thị bản đồ webp và các điểm tọa độ thiết bị
 * @param {string} locationName - Tên location để load ảnh tương ứng
 * @param {Array} devices - Danh sách thiết bị với tọa độ x, y (%)
 * @param {Function} getColor - Hàm lấy màu dựa trên device_id
 */
const MapViewer = ({ locationName, floorplanUrl, isLoading, hasError, devices, getColor }) => {

  // Nếu không có tên location, hiển thị placeholder báo lỗi ngay lập tức
  if (!locationName) {
    return (
      <div className="relative w-full bg-red-50 border border-red-100 rounded-xl overflow-hidden flex items-center justify-center" style={{ maxHeight: 'calc(100vh - 280px)' }}>
        <div className="text-center p-6">
          <div className="text-4xl mb-2">🗺️</div>
          <p className="text-red-500 font-bold">Chưa chọn khu vực</p>
          <p className="text-gray-400 text-xs mt-1">Vui lòng chọn bản đồ từ danh sách phía trên</p>
        </div>
      </div>
    );
  }

  if (!locationName || hasError) {
    return (
      <div className="relative w-full bg-gray-50 border border-gray-200 rounded-xl overflow-hidden shadow-inner min-h-[320px] flex items-center justify-center" style={{ maxHeight: 'calc(100vh - 280px)' }}>
        <div className="text-center p-6">
          <div className="text-4xl mb-2">🖼️</div>
          <p className="text-gray-700 font-bold">Không tìm thấy ảnh mặt bằng</p>
          <p className="text-gray-400 text-xs mt-1">Kiểm tra file {locationName}.webp trong thư mục floorplans</p>
        </div>
      </div>
    );
  }

  if (isLoading || !floorplanUrl) {
    return (
      <div className="relative w-full bg-gray-50 border border-gray-200 rounded-xl overflow-hidden shadow-inner min-h-[320px] flex items-center justify-center" style={{ maxHeight: 'calc(100vh - 280px)' }}>
        <div className="text-center p-6">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse mx-auto mb-3" />
          <p className="text-gray-700 font-bold">Đang tải mặt bằng...</p>
          <p className="text-gray-400 text-xs mt-1">{String(locationName || '').trim()}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full flex justify-center overflow-hidden">
      <div
        className="relative inline-block max-w-full bg-gray-50 border border-gray-200 rounded-xl overflow-hidden shadow-inner"
        style={{ maxHeight: 'calc(100vh - 280px)' }}
      >
        {/* Layer 0: Bản đồ nền */}
        <img
          src={floorplanUrl}
          key={floorplanUrl}
          alt={`Bản đồ ${locationName}`}
          className="block w-auto h-auto max-w-full max-h-full pointer-events-none"
        />

        {/* Layer 1: Các điểm tọa độ (Markers) */}
        <div className="absolute inset-0 z-10">
        {devices.map((device) => {
          if (device.x === null || device.y === null) return null;

          const color = getColor(device.device_id);

          return (
            <div
              key={device.device_id}
              className="absolute group"
              style={{
                left: `${device.x}%`,
                top: `${device.y}%`,
                transform: 'translate(-50%, -50%)',
                transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)'
              }}
            >
              {/* Hiệu ứng sóng nhấp nháy */}
              <div
                className="absolute inset-0 w-4 h-4 rounded-full animate-ping opacity-40"
                style={{ backgroundColor: color }}
              />

              {/* Chấm tọa độ chính */}
              <div
                className="relative w-3 h-3 rounded-full border-2 border-white shadow-lg cursor-pointer"
                style={{ backgroundColor: color }}
              />

              {/* Tooltip khi hover */}
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-20">
                <div className="bg-gray-900 text-white text-[10px] px-2 py-1 rounded shadow-xl whitespace-nowrap">
                  {device.device_id}
                </div>
              </div>
            </div>
          );
        })}
        </div>
      </div>
    </div>
  );
};

export default MapViewer;
