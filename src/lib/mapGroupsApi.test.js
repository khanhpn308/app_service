import { beforeEach, describe, expect, it, vi } from 'vitest';


const EXPECTED_EXPORTS = [
  'createMapGroup',
  'deleteMapGroup',
  'inviteMapGroupMember',
  'listMapGroupMembers',
  'listMapGroups',
  'listMyMapGroupInvitations',
  'removeMapGroupMember',
  'renameMapGroup',
  'respondToMapGroupInvitation',
];


describe('mapGroupsApi', () => {
  beforeEach(() => {
    localStorage.setItem('iot_token', 'test-token');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() =>
        Promise.resolve(
          new Response('{}', {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        ),
      ),
    );
  });

  it('exports the complete Phase 2 client contract', async () => {
    const api = await import('./mapGroupsApi');

    expect(Object.keys(api)).toEqual(expect.arrayContaining(EXPECTED_EXPORTS));
  });

  it('uses the documented REST paths and JSON methods', async () => {
    const api = await import('./mapGroupsApi');

    await api.listMapGroups();
    await api.createMapGroup({ name: 'Factory', owner_username: 'owner' });
    await api.renameMapGroup(7, 'Renamed');
    await api.deleteMapGroup(7);
    await api.listMapGroupMembers(7);
    await api.inviteMapGroupMember(7, 'member');
    await api.removeMapGroupMember(7, 9);
    await api.listMyMapGroupInvitations();
    await api.respondToMapGroupInvitation(7, 'accepted');

    expect(
      fetch.mock.calls.map(([path]) => new URL(path, 'http://local').pathname),
    ).toEqual([
      '/api/map-groups',
      '/api/map-groups',
      '/api/map-groups/7',
      '/api/map-groups/7',
      '/api/map-groups/7/members',
      '/api/map-groups/7/invitations',
      '/api/map-groups/7/members/9',
      '/api/map-group-invitations',
      '/api/map-group-invitations/7',
    ]);
    expect(fetch.mock.calls.map(([, options]) => options.method || 'GET')).toEqual([
      'GET',
      'POST',
      'PATCH',
      'DELETE',
      'GET',
      'POST',
      'DELETE',
      'GET',
      'PATCH',
    ]);
    expect(fetch.mock.calls[1][1].body).toBe(
      JSON.stringify({ name: 'Factory', owner_username: 'owner' }),
    );
    expect(fetch.mock.calls[8][1].body).toBe(
      JSON.stringify({ status: 'accepted' }),
    );
  });
});
