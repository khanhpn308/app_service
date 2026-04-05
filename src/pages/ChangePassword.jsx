import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock, AlertCircle, CheckCircle } from 'lucide-react';
import { apiFetch } from '../lib/api';

export default function ChangePassword() {
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [submitError, setSubmitError] = useState('');
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const validate = () => {
    const e = {};
    if (!currentPassword) e.current = 'Bắt buộc';
    if (!newPassword || newPassword.length < 6) e.new = 'Mật khẩu mới ít nhất 6 ký tự';
    if (newPassword.length > 45) e.new = 'Tối đa 45 ký tự';
    if (newPassword !== confirmPassword) e.confirm = 'Xác nhận không khớp';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (ev) => {
    ev.preventDefault();
    setSubmitError('');
    if (!validate()) return;
    setSubmitting(true);
    try {
      await apiFetch('/api/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
          confirm_password: confirmPassword,
        }),
      });
      setSuccess(true);
      setTimeout(() => navigate('/home'), 2000);
    } catch (err) {
      setSubmitError(err.message || 'Đổi mật khẩu thất bại');
    } finally {
      setSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className="max-w-md mx-auto space-y-4 text-center py-12">
        <CheckCircle className="h-16 w-16 text-green-500 mx-auto" />
        <h1 className="text-2xl font-bold text-white">Đổi mật khẩu thành công</h1>
        <p className="text-slate-400">Đang chuyển về Home...</p>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto">
      <h1 className="text-3xl font-bold text-white mb-2">Đổi mật khẩu</h1>
      <p className="text-slate-400 mb-8">Nhập mật khẩu hiện tại và mật khẩu mới</p>

      <form onSubmit={handleSubmit} className="space-y-6 bg-slate-800 rounded-xl p-8 border border-slate-700">
        {[
          ['current', 'Mật khẩu hiện tại', currentPassword, setCurrentPassword],
          ['new', 'Mật khẩu mới', newPassword, setNewPassword],
          ['confirm', 'Xác nhận mật khẩu mới', confirmPassword, setConfirmPassword],
        ].map(([key, label, val, setVal]) => (
          <div key={key}>
            <label className="block text-sm text-slate-300 mb-2">{label}</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
              <input
                type="password"
                value={val}
                onChange={(e) => setVal(e.target.value)}
                className={`w-full pl-10 pr-4 py-3 bg-slate-900 border rounded-lg text-white ${
                  errors[key] ? 'border-red-500' : 'border-slate-600'
                }`}
              />
            </div>
            {errors[key] && (
              <p className="text-red-400 text-sm mt-1 flex items-center gap-1">
                <AlertCircle className="h-4 w-4" />
                {errors[key]}
              </p>
            )}
          </div>
        ))}

        {submitError && (
          <div className="p-3 rounded-lg bg-red-900/40 border border-red-700 text-red-200 text-sm">{submitError}</div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg disabled:opacity-50"
        >
          {submitting ? 'Đang xử lý...' : 'Đổi mật khẩu'}
        </button>
      </form>
    </div>
  );
}
