import { apiFetch } from './api';


export function listMapGroups() {
  return apiFetch('/api/map-groups');
}


export function createMapGroup(input) {
  return apiFetch('/api/map-groups', {
    method: 'POST',
    body: JSON.stringify(input),
  });
}


export function renameMapGroup(groupId, name) {
  return apiFetch(`/api/map-groups/${groupId}`, {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  });
}


export function deleteMapGroup(groupId) {
  return apiFetch(`/api/map-groups/${groupId}`, { method: 'DELETE' });
}


export function listMapGroupMembers(groupId) {
  return apiFetch(`/api/map-groups/${groupId}/members`);
}


export function inviteMapGroupMember(groupId, username) {
  return apiFetch(`/api/map-groups/${groupId}/invitations`, {
    method: 'POST',
    body: JSON.stringify({ username }),
  });
}


export function removeMapGroupMember(groupId, userId) {
  return apiFetch(`/api/map-groups/${groupId}/members/${userId}`, {
    method: 'DELETE',
  });
}


export function listMyMapGroupInvitations() {
  return apiFetch('/api/map-group-invitations');
}


export function respondToMapGroupInvitation(groupId, status) {
  return apiFetch(`/api/map-group-invitations/${groupId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}
