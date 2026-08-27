import React, { useEffect, useRef, useState } from 'react';

const snapCoordinate = (value) => Math.round((Number(value) + Number.EPSILON) * 100) / 100

const MapViewer = ({ locationName, floorplanUrl, isLoading, hasError, devices, anchors = [], canConfigureAnchors = false, onAnchorClick, onAnchorMove, getColor, getDeviceName }) => {
  const [aspectRatio, setAspectRatio] = useState(null);
  const [frameSize, setFrameSize] = useState(null);
  const containerRef = useRef(null);
  const draggingAnchor = useRef(null);

  useEffect(() => {
    const container = containerRef.current
    if (!container || !aspectRatio) return undefined

    const fitFrame = () => {
      const { width: availableWidth, height: availableHeight } = container.getBoundingClientRect()
      if (!availableWidth || !availableHeight) return

      const availableRatio = availableWidth / availableHeight
      const width = aspectRatio >= availableRatio
        ? availableWidth
        : availableHeight * aspectRatio
      const height = aspectRatio >= availableRatio
        ? availableWidth / aspectRatio
        : availableHeight

      setFrameSize((current) => (
        current && Math.abs(current.width - width) < 0.5 && Math.abs(current.height - height) < 0.5
          ? current
          : { width, height }
      ))
    }

    fitFrame()
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', fitFrame)
      return () => window.removeEventListener('resize', fitFrame)
    }

    const observer = new ResizeObserver(fitFrame)
    observer.observe(container)
    return () => observer.disconnect()
  }, [aspectRatio])

  function moveAnchor(event) {
    if (!draggingAnchor.current || !onAnchorMove) return
    const rect = event.currentTarget.getBoundingClientRect()
    if (!rect.width || !rect.height) return
    const clamp = (value) => Math.max(0, Math.min(100, value))
    const x = snapCoordinate(clamp(((event.clientX - rect.left) / rect.width) * 100))
    const y = snapCoordinate(clamp(100 - ((event.clientY - rect.top) / rect.height) * 100))
    onAnchorMove(draggingAnchor.current, x, y)
  }

  if (!locationName) {
    return (
      <div className="relative flex h-full min-h-0 w-full flex-1 items-center justify-center overflow-hidden border border-red-200 bg-red-50">
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
      <div className="relative flex h-full min-h-0 w-full flex-1 items-center justify-center overflow-hidden border border-slate-300 bg-white">
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
      <div className="relative flex h-full min-h-0 w-full flex-1 items-center justify-center overflow-hidden border border-slate-300 bg-white">
        <div className="text-center p-6">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse mx-auto mb-3" />
          <p className="text-gray-700 font-bold">Đang tải mặt bằng...</p>
          <p className="text-gray-400 text-xs mt-1">{String(locationName || '').trim()}</p>
        </div>
      </div>
    );
  }

  const mapFrameStyle = frameSize
    ? { width: `${frameSize.width}px`, height: `${frameSize.height}px` }
    : { width: '100%', maxHeight: '100%', aspectRatio: aspectRatio || 'auto' };

  return (
    <div ref={containerRef} className="flex min-h-0 w-full flex-1 items-center justify-center overflow-hidden bg-white">
      <div
        className="relative w-full overflow-hidden bg-white"
        style={mapFrameStyle}
      >
        <img
          src={floorplanUrl}
          key={floorplanUrl}
          alt={`Bản đồ ${locationName}`}
          className="block h-full w-full pointer-events-none"
          onLoad={(event) => {
            const { naturalWidth, naturalHeight } = event.currentTarget;
            if (naturalWidth > 0 && naturalHeight > 0) {
              setAspectRatio(naturalWidth / naturalHeight);
            }
          }}
        />

        <div
          data-testid="map-coordinate-overlay"
          className="absolute inset-0 z-10 touch-none"
          onPointerMove={moveAnchor}
          onPointerUp={() => { draggingAnchor.current = null }}
          onPointerCancel={() => { draggingAnchor.current = null }}
        >
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
          {anchors.map((anchor) => {
            const x = snapCoordinate(anchor.x)
            const y = snapCoordinate(anchor.y)
            const style = {
              left: `${x}%`,
              top: `${snapCoordinate(100 - y)}%`,
              transform: 'translate(-50%, -50%)',
            }
            const markerClass = 'absolute z-20 flex -translate-y-0 flex-col items-center text-amber-700'
            const content = (
              <>
                <span className="h-4 w-4 rotate-45 rounded-sm border-2 border-white bg-amber-500 shadow-lg ring-2 ring-amber-700" />
                <span className="mt-1 max-w-24 truncate rounded bg-white/90 px-1.5 py-0.5 text-[10px] font-bold shadow">{anchor.name}</span>
              </>
            )
            if (!canConfigureAnchors) {
              return <div key={anchor.anchor_id ?? anchor.mac_address ?? anchor.hardware_id} aria-label={`Anchor ${anchor.name}`} className={markerClass} style={style}>{content}</div>
            }
            return (
              <button
                key={anchor.anchor_id ?? anchor.mac_address ?? anchor.hardware_id}
                type="button"
                aria-label={`Anchor ${anchor.name}`}
                className={`${markerClass} cursor-grab active:cursor-grabbing`}
                style={style}
                onPointerDown={(event) => {
                  event.currentTarget.setPointerCapture?.(event.pointerId)
                  draggingAnchor.current = anchor
                  onAnchorClick?.(anchor)
                }}
              >
                {content}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  );
};

export default MapViewer;
