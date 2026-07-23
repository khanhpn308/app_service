import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';


describe('Map group manager integration contract', () => {
  it('adds the manager dialog to the GPS toolbar', async () => {
    const dashboard = await readFile(
      resolve('src/components/Dashboard/GPS/GPSDashboard.jsx'),
      'utf8',
    );

    expect(dashboard).toContain("import MapGroupManagerDialog from './MapGroupManagerDialog'");
    expect(dashboard).toContain('<MapGroupManagerDialog');
  });

  it('provides a dedicated dialog and API client module', async () => {
    const dialog = await readFile(
      resolve('src/components/Dashboard/GPS/MapGroupManagerDialog.jsx'),
      'utf8',
    );
    expect(dialog).toContain('MapGroupManagerDialog');
    expect(dialog).toContain('Quản lý nhóm');
    await expect(
      readFile(resolve('src/lib/mapGroupsApi.js'), 'utf8'),
    ).resolves.toContain('listMapGroups');
  });
});
