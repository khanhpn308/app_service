import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach } from 'vitest';
import { expect, test } from 'vitest';

import MapViewer from './MapViewer.jsx';

const mapViewerPath = resolve(
  process.cwd(),
  'src/components/Dashboard/GPS/MapViewer.jsx',
);

afterEach(cleanup);

test('coordinate overlay fits the complete floorplan inside the available viewport', async () => {
  const source = await readFile(mapViewerPath, 'utf8');

  expect(source).toMatch(/ResizeObserver/);
  expect(source).toMatch(/frameSize/);
  expect(source).toMatch(/onLoad=/);
  expect(source).toMatch(/aspectRatio/);
  expect(source).not.toMatch(/1200px/);
  expect(source).not.toMatch(/100dvh/);
  expect(source).toMatch(/className="block h-full w-full pointer-events-none"/);
  expect(source).not.toMatch(/overflow-auto/);
  expect(source).not.toMatch(/max-h-full/);
});

test('uses a Cartesian Y axis with zero at the bottom of the map', async () => {
  const source = await readFile(mapViewerPath, 'utf8');

  expect(source).toMatch(/top: `\$\{100 - device\.y\}%`/);
});

test('shows the device name as unboxed text in the marker color', () => {
  const longName = 'GPS tracker with a deliberately long database name';
  render(React.createElement(MapViewer, {
    locationName: 'FLOOR_1',
    floorplanUrl: 'blob:floor-1',
    isLoading: false,
    hasError: false,
    devices: [
      { device_id: 662168, devicename: 'GPS3', x: 25, y: 44 },
      { device_id: 99, devicename: longName, x: 40, y: 50 },
    ],
    getColor: () => '#ec4899',
    getDeviceName: (device) => device.devicename,
  }));

  const gpsLabel = screen.getByText('GPS3');
  const longLabel = screen.getByText(longName);

  expect(gpsLabel.className).toContain('truncate');
  expect(gpsLabel.className).not.toContain('hidden');
  expect(gpsLabel.className).not.toMatch(/\b(bg-|rounded|px-|py-|shadow|text-white)/);
  expect(gpsLabel.style.color).toBe('rgb(236, 72, 153)');
  expect(gpsLabel.getAttribute('title')).toBe('GPS3');
  expect(longLabel.getAttribute('title')).toBe(longName);
  expect(screen.queryByText('662168')).toBeNull();
});
