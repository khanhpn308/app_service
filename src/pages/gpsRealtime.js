function toFiniteNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function getDeviceId(value) {
  return value?.device_id ?? value?.deviceId ?? value?.id ?? null;
}

function getTimestampIso(update) {
  if (update?.ts_iso) return String(update.ts_iso);

  const milliseconds = toFiniteNumber(update?.server_receive_ms ?? update?.timestamp_ms);
  if (milliseconds !== null) return new Date(milliseconds).toISOString();

  const seconds = toFiniteNumber(update?.ts);
  return seconds !== null ? new Date(seconds * 1000).toISOString() : null;
}

function getGpsUpdates(message) {
  const candidates = Array.isArray(message?.devices) ? message.devices : [message];

  return candidates.flatMap((update) => {
    const deviceId = getDeviceId(update);
    const x = toFiniteNumber(update?.x);
    const y = toFiniteNumber(update?.y);
    const sensorType = String(update?.sensor_type ?? update?.sensorType ?? '').toLowerCase();
    const isGps = sensorType === 'gps' || (!sensorType && x !== null && y !== null);

    if (deviceId === null || !isGps || x === null || y === null) return [];

    return [{
      device_id: deviceId,
      x,
      y,
      location: String(update?.location ?? update?.loc ?? '').trim() || null,
      ts_iso: getTimestampIso(update),
    }];
  });
}

export function mergeGpsMessage(devices, message) {
  const updates = getGpsUpdates(message);
  if (updates.length === 0) return devices;

  const next = [...devices];
  updates.forEach((update) => {
    const index = next.findIndex(
      (device) => String(getDeviceId(device)) === String(update.device_id)
    );

    if (index === -1) {
      next.push({
        device_id: update.device_id,
        x: update.x,
        y: update.y,
        location: update.location || 'unknown',
        ts_iso: update.ts_iso,
      });
      return;
    }

    const current = next[index];
    next[index] = {
      ...current,
      x: update.x,
      y: update.y,
      location: update.location || current.location || 'unknown',
      ts_iso: update.ts_iso || current.ts_iso || null,
    };
  });

  return next;
}

export function mergeDeviceCatalog(liveDevices, catalog) {
  const liveById = new Map(
    liveDevices.map((device) => [String(getDeviceId(device)), device])
  );

  const merged = catalog.map((device) => {
    const live = liveById.get(String(getDeviceId(device)));
    liveById.delete(String(getDeviceId(device)));

    return {
      ...device,
      x: live?.x ?? null,
      y: live?.y ?? null,
      location: live?.location || device.location || 'unknown',
      ...(live?.ts_iso ? { ts_iso: live.ts_iso } : {}),
    };
  });

  return [...merged, ...liveById.values()];
}
