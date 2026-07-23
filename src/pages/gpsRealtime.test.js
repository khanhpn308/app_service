import { expect, test } from 'vitest';

import { mergeDeviceCatalog, mergeGpsMessage } from './gpsRealtime.js';

test('mergeGpsMessage updates coordinates immediately for a GPS payload', () => {
  const devices = [{ device_id: 101, location: 'Floor_1', x: null, y: null }];

  const result = mergeGpsMessage(devices, {
    device_id: '101',
    sensor_type: 'gps',
    x: 42.5,
    y: 18.25,
    location: 'Floor_2',
    server_receive_ms: 1_721_234_567_890,
  });

  expect(result).toEqual([
    {
      device_id: 101,
      location: 'Floor_2',
      x: 42.5,
      y: 18.25,
      ts_iso: new Date(1_721_234_567_890).toISOString(),
    },
  ]);
});

test('mergeGpsMessage ignores non-GPS telemetry', () => {
  const devices = [{ device_id: 101, location: 'Floor_1', x: 5, y: 10 }];

  const result = mergeGpsMessage(devices, {
    device_id: '101',
    sensor_type: 'temperature',
    temperature: 28,
  });

  expect(result).toBe(devices);
});

test('mergeDeviceCatalog preserves a realtime position received before the catalog', () => {
  const liveDevices = [{ device_id: '101', x: 20, y: 30, location: 'Floor_2' }];
  const catalog = [{ device_id: 101, devicename: 'Tracker 101', location: 'Floor_1' }];

  expect(mergeDeviceCatalog(liveDevices, catalog)).toEqual([
    {
      device_id: 101,
      devicename: 'Tracker 101',
      location: 'Floor_2',
      x: 20,
      y: 30,
    },
  ]);
});

test('mergeGpsMessage accepts backend batches and discovers a new tracker', () => {
  const result = mergeGpsMessage([], {
    devices: [
      { deviceId: 202, sensorType: 'gps', x: '12.5', y: '44', location: 'Floor_3' },
    ],
  });

  expect(result).toEqual([
    {
      device_id: 202,
      x: 12.5,
      y: 44,
      location: 'Floor_3',
      ts_iso: null,
    },
  ]);
});
