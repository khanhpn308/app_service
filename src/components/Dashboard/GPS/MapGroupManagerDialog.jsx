import { useCallback, useState } from 'react'
import { Users } from 'lucide-react'

import { useAuth } from '@/contexts/AuthContext'
import {
  createMapGroup,
  deleteMapGroup,
  inviteMapGroupMember,
  listMapGroupMembers,
  listMapGroups,
  listMyMapGroupInvitations,
  removeMapGroupMember,
  renameMapGroup,
  respondToMapGroupInvitation,
} from '@/lib/mapGroupsApi'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

import GroupEditor from './GroupEditor'
import GroupListPanel from './GroupListPanel'
import InvitationPanel from './InvitationPanel'
import DeletedMapsPanel from './DeletedMapsPanel'

function MapGroupManagerDialog({ onGroupsChanged }) {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('groups')
  const [groups, setGroups] = useState([])
  const [invitations, setInvitations] = useState([])
  const [selectedGroup, setSelectedGroup] = useState(null)
  const [members, setMembers] = useState([])
  const [loading, setLoading] = useState(false)
  const [membersLoading, setMembersLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const loadOverview = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [nextGroups, nextInvitations] = await Promise.all([
        listMapGroups(),
        listMyMapGroupInvitations(),
      ])
      setGroups(nextGroups)
      setInvitations(nextInvitations)
    } catch (requestError) {
      setError(requestError.message || 'Không thể tải dữ liệu nhóm bản đồ.')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadMembers = useCallback(async (groupId) => {
    setMembersLoading(true)
    setError('')
    try {
      setMembers(await listMapGroupMembers(groupId))
    } catch (requestError) {
      setError(requestError.message || 'Không thể tải danh sách thành viên.')
    } finally {
      setMembersLoading(false)
    }
  }, [])

  const handleOpenChange = (nextOpen) => {
    setOpen(nextOpen)
    if (nextOpen) {
      loadOverview()
      return
    }
    setActiveTab('groups')
    setSelectedGroup(null)
    setMembers([])
    setError('')
  }

  const handleCreate = async (payload) => {
    setBusy(true)
    setError('')
    try {
      await createMapGroup(payload)
      await loadOverview()
      await onGroupsChanged?.()
    } catch (requestError) {
      setError(requestError.message || 'Không thể tạo nhóm.')
    } finally {
      setBusy(false)
    }
  }

  const handleManage = async (group) => {
    setSelectedGroup(group)
    await loadMembers(group.group_id)
  }

  const handleRename = async (name) => {
    setBusy(true)
    setError('')
    try {
      const updatedGroup = await renameMapGroup(selectedGroup.group_id, name)
      setSelectedGroup(updatedGroup)
      setGroups((current) =>
        current.map((group) =>
          group.group_id === updatedGroup.group_id ? updatedGroup : group,
        ),
      )
    } catch (requestError) {
      setError(requestError.message || 'Không thể đổi tên nhóm.')
    } finally {
      setBusy(false)
    }
  }

  const handleInvite = async (username) => {
    setBusy(true)
    setError('')
    try {
      await inviteMapGroupMember(selectedGroup.group_id, username)
      await loadMembers(selectedGroup.group_id)
    } catch (requestError) {
      setError(requestError.message || 'Không thể gửi lời mời.')
    } finally {
      setBusy(false)
    }
  }

  const handleRemoveMember = async (member) => {
    setBusy(true)
    setError('')
    try {
      await removeMapGroupMember(selectedGroup.group_id, member.user_id)
      await loadMembers(selectedGroup.group_id)
    } catch (requestError) {
      setError(requestError.message || 'Không thể gỡ thành viên.')
    } finally {
      setBusy(false)
    }
  }

  const handleDelete = async () => {
    const confirmed = window.confirm(
      `Xóa nhóm “${selectedGroup.name}”? Tất cả map đang sử dụng sẽ được chuyển vào lịch sử đã xóa.`,
    )
    if (!confirmed) return

    setBusy(true)
    setError('')
    try {
      await deleteMapGroup(selectedGroup.group_id)
      setSelectedGroup(null)
      setMembers([])
      await loadOverview()
      await onGroupsChanged?.()
    } catch (requestError) {
      setError(requestError.message || 'Không thể xóa nhóm.')
    } finally {
      setBusy(false)
    }
  }

  const handleInvitationResponse = async (invitation, status) => {
    setBusy(true)
    setError('')
    try {
      await respondToMapGroupInvitation(invitation.group_id, status)
      setInvitations(await listMyMapGroupInvitations())
      if (status === 'accepted') {
        setGroups(await listMapGroups())
        await onGroupsChanged?.()
      }
    } catch (requestError) {
      setError(requestError.message || 'Không thể cập nhật lời mời.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" className="gap-2">
          <Users className="h-4 w-4" aria-hidden="true" />
          Quản lý nhóm
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>Quản lý nhóm bản đồ</DialogTitle>
          <DialogDescription>
            Tạo nhóm, mời thành viên và quản lý quyền truy cập các bản đồ GPS.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap gap-2 border-b pb-3">
          <Button
            type="button"
            variant={activeTab === 'groups' ? 'default' : 'ghost'}
            aria-pressed={activeTab === 'groups'}
            onClick={() => setActiveTab('groups')}
          >
            Nhóm của tôi
          </Button>
          <Button
            type="button"
            variant={activeTab === 'invitations' ? 'default' : 'ghost'}
            aria-pressed={activeTab === 'invitations'}
            onClick={() => setActiveTab('invitations')}
          >
            Lời mời ({invitations.length})
          </Button>
          {user?.role?.toLowerCase() === 'admin' && (
            <Button
              type="button"
              variant={activeTab === 'deleted' ? 'default' : 'ghost'}
              aria-pressed={activeTab === 'deleted'}
              onClick={() => setActiveTab('deleted')}
            >
              Lịch sử map đã xóa
            </Button>
          )}
        </div>

        {error && (
          <div
            role="alert"
            className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            <span>{error}</span>
            <Button type="button" size="sm" variant="outline" onClick={loadOverview}>
              Thử lại
            </Button>
          </div>
        )}

        {activeTab === 'deleted' ? (
          <DeletedMapsPanel />
        ) : loading ? (
          <div role="status" className="py-10 text-center text-sm text-slate-500">
            Đang tải dữ liệu nhóm...
          </div>
        ) : activeTab === 'invitations' ? (
          <InvitationPanel
            invitations={invitations}
            isBusy={busy}
            onRespond={handleInvitationResponse}
          />
        ) : selectedGroup ? (
          <GroupEditor
            group={selectedGroup}
            members={members}
            isLoading={membersLoading}
            isBusy={busy}
            onBack={() => {
              setSelectedGroup(null)
              setMembers([])
            }}
            onRename={handleRename}
            onInvite={handleInvite}
            onRemove={handleRemoveMember}
            onDelete={handleDelete}
          />
        ) : (
          <GroupListPanel
            groups={groups}
            isAdmin={user?.role === 'admin'}
            isBusy={busy}
            onCreate={handleCreate}
            onManage={handleManage}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

export default MapGroupManagerDialog
