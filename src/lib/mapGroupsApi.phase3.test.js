import { beforeEach, describe, expect, it, vi } from 'vitest'

import { inviteMapGroupMembersBulk } from './mapGroupsApi'
import { apiFetch } from './api'

vi.mock('./api', () => ({ apiFetch: vi.fn() }))

describe('Phase 3 mapGroupsApi', () => {
  beforeEach(() => apiFetch.mockReset().mockResolvedValue({}))

  it('posts the bulk invitation contract', async () => {
    await inviteMapGroupMembersBulk(4, ['user01', 'user02'])
    expect(apiFetch).toHaveBeenCalledWith('/api/map-groups/4/invitations/bulk', {
      method: 'POST',
      body: JSON.stringify({ usernames: ['user01', 'user02'] }),
    })
  })
})
