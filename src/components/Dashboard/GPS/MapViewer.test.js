import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

test('coordinate overlay uses the same responsive 800px frame as the floorplan image', async () => {
  const source = await readFile(new URL('./MapViewer.jsx', import.meta.url), 'utf8');

  assert.match(source, /max-w-\[800px\]/);
  assert.match(source, /onLoad=/);
  assert.match(source, /aspectRatio/);
  assert.match(source, /calc\(\(100vh - 360px\) \*/);
  assert.match(source, /className="block w-full h-full pointer-events-none"/);
  assert.doesNotMatch(source, /overflow-auto/);
  assert.doesNotMatch(source, /max-h-full/);
});

test('uses a Cartesian Y axis with zero at the bottom of the map', async () => {
  const source = await readFile(new URL('./MapViewer.jsx', import.meta.url), 'utf8');

  assert.match(source, /top: `\$\{100 - device\.y\}%`/);
});
