import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { expect, test } from 'vitest';

const mapViewerPath = resolve(
  process.cwd(),
  'src/components/Dashboard/GPS/MapViewer.jsx',
);

test('coordinate overlay uses the same responsive 800px frame as the floorplan image', async () => {
  const source = await readFile(mapViewerPath, 'utf8');

  expect(source).toMatch(/max-w-\[800px\]/);
  expect(source).toMatch(/onLoad=/);
  expect(source).toMatch(/aspectRatio/);
  expect(source).toMatch(/calc\(\(100vh - 360px\) \*/);
  expect(source).toMatch(/className="block w-full h-full pointer-events-none"/);
  expect(source).not.toMatch(/overflow-auto/);
  expect(source).not.toMatch(/max-h-full/);
});

test('uses a Cartesian Y axis with zero at the bottom of the map', async () => {
  const source = await readFile(mapViewerPath, 'utf8');

  expect(source).toMatch(/top: `\$\{100 - device\.y\}%`/);
});
