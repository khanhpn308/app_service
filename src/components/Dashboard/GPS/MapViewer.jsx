import React, { useState } from 'react';

const MapViewer = ({ locationName, floorplanUrl, isLoading, hasError, devices, getColor, getDeviceName }) => {
  const [aspectRatio, setAspectRatio] = useState(null);

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

  if (hasError) {
    return (
      <div className="relative w-full bg-gray-50 border border-gray-200 rounded-xl overflow-hidden shadow-inner min-h-[320px] flex items-center justify-center" style={{ maxHeight: 'calc(100vh - 280px)' }}>
        <div className="text-center p-6">
          <div className="text-4xl mb-2">🖼️</div>
          <p className="text-gray-700 font-bold">Không tìm thấy ảnh mặt bằng</p>
          <p className="text-gray-400 text-xs mt-1">
            Kiểm tra quyền truy cập hoặc thử tải lại ảnh của {locationName}
          </p>
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

  const mapFrameStyle = aspectRatio
    ? {
        width: `min(100%, 800px, calc((100vh - 360px) * ${aspectRatio}))`,
        aspectRatio,
      }
    : { width: 'min(100%, 800px)' };

  return (
    <div className="w-full flex justify-center overflow-hidden">
      <div
        className="relative mx-auto w-full max-w-[800px] bg-gray-50 border border-gray-200 rounded-xl overflow-hidden shadow-inner"
        style={mapFrameStyle}
      >
        <img
          src={floorplanUrl}
          key={floorplanUrl}
          alt={`Bản đồ ${locationName}`}
          className="block w-full h-full pointer-events-none"
          onLoad={(event) => {
            const { naturalWidth, naturalHeight } = event.currentTarget;
            if (naturalWidth > 0 && naturalHeight > 0) {
              setAspectRatio(naturalWidth / naturalHeight);
            }
          }}
        />

        <div className="absolute inset-0 z-10">
          {devices.map((device) => {
            if (device.x === null || device.y === null) return null;

            const color = getColor(device.device_id);
            const deviceName = getDeviceName(device);

            return (
              <div
                key={device.device_id}
                className="absolute group"
                style={{
                  left: `${device.x}%`,
                  top: `${100 - device.y}%`,
                  transform: 'translate(-50%, -50%)',
                  transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
                }}
              >
                <div
                  className="absolute inset-0 w-4 h-4 rounded-full animate-ping opacity-40"
                  style={{ backgroundColor: color }}
                />

                <div
                  className="relative w-3 h-3 rounded-full border-2 border-white shadow-lg cursor-pointer"
                  style={{ backgroundColor: color }}
                />

                <div
                  title={deviceName}
                  aria-label={`Thiết bị ${deviceName}`}
                  className="absolute bottom-full left-1/2 z-20 mb-2 max-w-[8rem] -translate-x-1/2 truncate whitespace-nowrap text-[10px] font-bold"
                  style={{ color }}
                >
                  {deviceName}
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
