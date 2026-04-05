import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Plus, Search, Users, X, Trash2, Eye, EyeOff } from 'lucide-react';
import { apiFetch } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import AssignDeviceModal from '../components/AssignDeviceModal';

function defaultExpiredAt() {
  const d = new Date();
  d.setFullYear(d.getFullYear() + 1);
  return d.toISOString().slice(0, 10);
}

/** ISO yyyy-mm-dd → hiển thị dd/mm/yyyy */
function isoToDdMmYyyy(iso) {
  if (!iso || typeof iso !== 'string') return '';
  const [y, m, d] = iso.slice(0, 10).split('-');
  if (!y || !m || !d) return '';
  return `${d}/${m}/${y}`;
}

/** Chuỗi dd/mm/yyyy (hoặc d/m/yyyy) → ISO yyyy-mm-dd, không hợp lệ → null */
function ddMmYyyyToIso(s) {
  const t = String(s).trim();
  const match = t.match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/);
  if (!match) return null;
  const day = parseInt(match[1], 10);
  const month = parseInt(match[2], 10);
  const year = parseInt(match[3], 10);
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  const dt = new Date(year, month - 1, day);
  if (dt.getFullYear() !== year || dt.getMonth() !== month - 1 || dt.getDate() !== day) {
    return null;
  }
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

const emptyForm = () => ({
  username: '',
  password: '',
  confirm_password: '',
  fullname: '',
  cccd: '',
  email: '',
  phone: '',
  expired_at: defaultExpiredAt(),
  role: 'user',
});

export default function UserManagement() {
  const { user: currentUser } = useAuth();
  const [searchTerm, setSearchTerm] = useState('');
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState(emptyForm());
  const [submitError, setSubmitError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState('');
  const [deleteError, setDeleteError] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [statusPatchingId, setStatusPatchingId] = useState(null);
  const [showPassword, setShowPassword] = useState(false);
  const [assignTarget, setAssignTarget] = useState(null);
  /** Ô ngày hết hạn (đăng ký): hiển thị dd/mm/yyyy, không phụ thuộc locale của type="date" */
  const [expiredAtDisplay, setExpiredAtDisplay] = useState(() =>
    isoToDdMmYyyy(defaultExpiredAt())
  );

  const loadUsers = useCallback(async () => {
    setLoadError('');
    setLoading(true);
    try {
      const list = await apiFetch('/api/users');
      setUsers(Array.isArray(list) ? list : []);
    } catch (e) {
      setLoadError(e.message || 'Không tải được danh sách');
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const filteredUsers = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    if (!q) return users;
    return users.filter(
      (u) =>
        u.username.toLowerCase().includes(q) ||
        (u.email && u.email.toLowerCase().includes(q)) ||
        String(u.user_id).includes(q) ||
        u.fullname.toLowerCase().includes(q)
    );
  }, [searchTerm, users]);

  const openModal = () => {
    const f = emptyForm();
    setForm(f);
    setExpiredAtDisplay(isoToDdMmYyyy(f.expired_at));
    setShowPassword(false);
    setSubmitError('');
    setModalOpen(true);
  };

  const handleStatusChange = async (userId, newStatus) => {
    setStatusPatchingId(userId);
    setLoadError('');
    try {
      await apiFetch(`/api/users/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus }),
      });
      await loadUsers();
    } catch (e) {
      setLoadError(e.message || 'Cập nhật trạng thái thất bại');
    } finally {
      setStatusPatchingId(null);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setSubmitError('');
    setSubmitting(true);
    try {
      if (!form.password || form.password.length < 6 || form.password.length > 45) {
        throw new Error('Mật khẩu phải từ 6 đến 45 ký tự');
      }
      if (form.password !== form.confirm_password) {
        throw new Error('Mật khẩu xác nhận không khớp');
      }
      const cccdStr = String(form.cccd).replace(/\D/g, '');
      if (cccdStr.length !== 12) {
        throw new Error('CCCD phải đúng 12 chữ số');
      }
      const phoneVal =
        form.phone === '' || form.phone == null
          ? null
          : parseInt(String(form.phone).replace(/\D/g, ''), 10);
      if (phoneVal != null && Number.isNaN(phoneVal)) {
        throw new Error('Số điện thoại không hợp lệ');
      }
      const expiredIso = ddMmYyyyToIso(expiredAtDisplay.trim());
      if (!expiredIso) {
        throw new Error('Ngày hết hạn không hợp lệ. Nhập theo định dạng dd/mm/yyyy');
      }
      if (expiredIso < todayIso()) {
        throw new Error('Ngày hết hạn không được trước hôm nay');
      }
      await apiFetch('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          username: form.username.trim(),
          password: form.password,
          fullname: form.fullname.trim(),
          cccd: cccdStr,
          email: form.email.trim() || null,
          phone: phoneVal,
          expired_at: expiredIso,
          role: form.role,
        }),
      });
      setModalOpen(false);
      await loadUsers();
    } catch (err) {
      setSubmitError(err.message || 'Đăng ký thất bại');
    } finally {
      setSubmitting(false);
    }
  };

  const openDelete = (u) => {
    setDeleteTarget(u);
    setDeleteConfirm('');
    setDeleteError('');
  };

  const openAssign = (u) => {
    setAssignTarget(u);
  };

  const handleDelete = async () => {
    if (deleteConfirm !== 'OK') {
      setDeleteError('Nhập chính xác OK (chữ in hoa)');
      return;
    }
    setDeleteError('');
    setDeleting(true);
    try {
      await apiFetch(`/api/users/${deleteTarget.user_id}`, { method: 'DELETE' });
      setDeleteTarget(null);
      await loadUsers();
    } catch (err) {
      setDeleteError(err.message || 'Xóa thất bại');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Quản lý người dùng</h1>
          <p className="text-slate-400">Chỉ admin mới tạo tài khoản mới tại đây</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center space-x-2 bg-slate-800 px-4 py-2 rounded-lg border border-slate-700">
            <Users className="h-5 w-5 text-blue-500" />
            <span className="text-slate-300 text-sm">{users.length} tài khoản</span>
          </div>
          <button
            type="button"
            onClick={openModal}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg"
          >
            <Plus className="h-5 w-5" />
            Đăng ký tài khoản
          </button>
        </div>
      </div>

      {loadError && (
        <div className="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-200 text-sm">{loadError}</div>
      )}

      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
          <Search className="h-5 w-5 text-slate-400" />
        </div>
        <input
          type="text"
          placeholder="Tìm theo tên, username, email, ID..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-11 pr-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {loading ? (
        <p className="text-slate-400">Đang tải...</p>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {filteredUsers.map((u) => (
            <div
              key={u.user_id}
              className="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-lg"
            >
              <div className="flex items-start justify-between mb-4 gap-2">
                <div className="min-w-0 flex-1">
                  <h3 className="text-lg font-bold text-white">{u.fullname}</h3>
                  <p className="text-slate-400 text-sm">@{u.username}</p>
                  {u.email && <p className="text-slate-500 text-sm">{u.email}</p>}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-semibold ${
                      u.role === 'admin'
                        ? 'bg-purple-500/20 text-purple-400'
                        : 'bg-blue-500/20 text-blue-400'
                    }`}
                  >
                    {u.role.toUpperCase()}
                  </span>
                  {u.role === 'user' && (
                    <button
                      type="button"
                      onClick={() => openAssign(u)}
                      className="px-3 py-2 rounded-lg bg-slate-900 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold"
                      title="Phân quyền thiết bị"
                    >
                      Phân quyền
                    </button>
                  )}
                  {currentUser?.user_id !== u.user_id && (
                    <button
                      type="button"
                      onClick={() => openDelete(u)}
                      className="p-2 rounded-lg bg-red-900/40 hover:bg-red-900/70 text-red-300 border border-red-800"
                      title="Xóa người dùng"
                    >
                      <Trash2 className="h-5 w-5" />
                    </button>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-slate-900 rounded-lg p-3 border border-slate-700">
                  <p className="text-slate-500 text-xs mb-1">ID</p>
                  <p className="text-blue-400 font-mono font-semibold">{u.user_id}</p>
                </div>
                <div className="bg-slate-900 rounded-lg p-3 border border-slate-700">
                  <p className="text-slate-500 text-xs mb-1">Còn lại (ngày)</p>
                  <p className="text-slate-200 font-semibold">
                    {u.remaining_days != null ? u.remaining_days : '—'}
                  </p>
                </div>
                <div className="bg-slate-900 rounded-lg p-3 border border-slate-700">
                  <p className="text-slate-500 text-xs mb-1">Ngày hết hạn</p>
                  <p className="text-slate-200">
                    {u.expired_at ? isoToDdMmYyyy(String(u.expired_at).slice(0, 10)) : '—'}
                  </p>
                </div>
                <div className="bg-slate-900 rounded-lg p-3 border border-slate-700 col-span-2">
                  <p className="text-slate-500 text-xs mb-1">Trạng thái</p>
                  <select
                    value={u.status}
                    disabled={
                      currentUser?.user_id === u.user_id || statusPatchingId === u.user_id
                    }
                    onChange={(e) => handleStatusChange(u.user_id, e.target.value)}
                    className="w-full max-w-xs px-3 py-2 bg-slate-950 border border-slate-600 rounded-lg text-white text-sm disabled:opacity-50"
                  >
                    <option value="active">active</option>
                    <option value="deactive">deactive</option>
                  </select>
                  {currentUser?.user_id === u.user_id && (
                    <p className="text-slate-500 text-[10px] mt-1">Không đổi trạng thái tài khoản đang đăng nhập</p>
                  )}
                </div>
                <div className="bg-slate-900 rounded-lg p-3 border border-slate-700">
                  <p className="text-slate-500 text-xs mb-1">Điện thoại</p>
                  <p className="text-slate-200">{u.phone ?? '—'}</p>
                </div>
                <div className="bg-slate-900 rounded-lg p-3 border border-slate-700">
                  <p className="text-slate-500 text-xs mb-1">Ngày tạo</p>
                  <p className="text-slate-200">{u.creat_at}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && filteredUsers.length === 0 && (
        <div className="text-center py-12">
          <Users className="h-16 w-16 text-slate-600 mx-auto mb-4" />
          <p className="text-slate-400 text-lg">Không có người dùng</p>
        </div>
      )}

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
          <div className="bg-slate-800 border border-slate-700 rounded-xl max-w-lg w-full max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="flex items-center justify-between p-4 border-b border-slate-700">
              <h2 className="text-lg font-semibold text-white">Đăng ký tài khoản</h2>
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="p-2 rounded-lg hover:bg-slate-700 text-slate-400"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleRegister} className="p-4 space-y-4">
              {[
                ['username', 'Tên đăng nhập', 'text'],
                ['fullname', 'Họ và tên', 'text'],
                ['cccd', 'CCCD (12 số)', 'text'],
                ['email', 'Email', 'email'],
                ['phone', 'Số điện thoại (số nguyên)', 'text'],
              ].map(([key, label, type]) => (
                <div key={key}>
                  <label className="block text-sm text-slate-300 mb-1">{label}</label>
                  <input
                    type={type}
                    required={key !== 'email' && key !== 'phone'}
                    value={form[key]}
                    onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white"
                  />
                </div>
              ))}
              <div>
                <label className="block text-sm text-slate-300 mb-1">Mật khẩu</label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={form.password}
                    onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                    className="w-full pr-10 px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute inset-y-0 right-0 px-3 text-slate-400 hover:text-slate-200"
                    aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                    title={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                  >
                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">Xác nhận mật khẩu</label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={form.confirm_password}
                    onChange={(e) => setForm((f) => ({ ...f, confirm_password: e.target.value }))}
                    className="w-full pr-10 px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute inset-y-0 right-0 px-3 text-slate-400 hover:text-slate-200"
                    aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                    title={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                  >
                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">
                  Ngày hết hạn (tài khoản active đến hết ngày này)
                </label>
                <input
                  type="text"
                  inputMode="numeric"
                  autoComplete="off"
                  placeholder="dd/mm/yyyy"
                  value={expiredAtDisplay}
                  onChange={(e) => setExpiredAtDisplay(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white placeholder-slate-500"
                />
                <p className="text-slate-500 text-xs mt-1">
                  Định dạng: <span className="text-slate-400">dd/mm/yyyy</span> (ví dụ 31/12/2026). Trạng thái mặc định
                  khi tạo: <span className="text-slate-400">active</span>
                </p>
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">Vai trò</label>
                <select
                  value={form.role}
                  onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white"
                >
                  <option value="user">user</option>
                  <option value="admin">admin</option>
                </select>
              </div>
              {submitError && (
                <div className="p-3 rounded bg-red-900/30 border border-red-700 text-red-200 text-sm">{submitError}</div>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 rounded-lg border border-slate-600 text-slate-300 hover:bg-slate-700"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
                >
                  {submitting ? 'Đang lưu...' : 'Tạo tài khoản'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70">
          <div className="bg-slate-800 border border-red-900/50 rounded-xl max-w-md w-full shadow-2xl p-6">
            <h3 className="text-lg font-bold text-white mb-2">Xác nhận xóa người dùng</h3>
            <p className="text-slate-300 text-sm mb-4">
              Bạn sắp xóa vĩnh viễn tài khoản:
            </p>
            <ul className="text-slate-200 text-sm mb-4 space-y-1 list-disc list-inside">
              <li>
                <span className="text-slate-400">Tên:</span> {deleteTarget.fullname}
              </li>
              <li>
                <span className="text-slate-400">Username:</span> @{deleteTarget.username}
              </li>
              <li>
                <span className="text-slate-400">ID:</span> {deleteTarget.user_id}
              </li>
            </ul>
            <p className="text-amber-200/90 text-xs mb-3">
              Nhập <strong className="text-white">OK</strong> (chữ in hoa) vào ô bên dưới để xác nhận.
            </p>
            <input
              type="text"
              value={deleteConfirm}
              onChange={(e) => setDeleteConfirm(e.target.value)}
              placeholder="OK"
              className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white mb-3 font-mono"
            />
            {deleteError && (
              <p className="text-red-400 text-sm mb-3">{deleteError}</p>
            )}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeleteTarget(null)}
                className="px-4 py-2 rounded-lg border border-slate-600 text-slate-300 hover:bg-slate-700"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleting}
                className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white disabled:opacity-50"
              >
                {deleting ? 'Đang xóa...' : 'Xóa khỏi database'}
              </button>
            </div>
          </div>
        </div>
      )}

      {assignTarget && (
        <AssignDeviceModal
          user={assignTarget}
          currentAdmin={currentUser}
          onClose={() => setAssignTarget(null)}
          onSuccess={loadUsers}
        />
      )}
    </div>
  );
}
