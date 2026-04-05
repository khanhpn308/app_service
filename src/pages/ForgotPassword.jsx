import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Cpu, User, Hash, AlertCircle, CheckCircle } from 'lucide-react';
import { apiFetch } from '../lib/api';

const ForgotPassword = () => {
  const [username, setUsername] = useState('');
  const [cccd, setCccd] = useState('');
  const [errors, setErrors] = useState({});
  const [submitError, setSubmitError] = useState('');
  const [result, setResult] = useState(null);
  
  const validateForm = () => {
    const newErrors = {};
    if (!username.trim()) newErrors.username = 'Nhập tên đăng nhập';
    const digits = String(cccd).replace(/\D/g, '');
    if (digits.length !== 12) newErrors.cccd = 'CCCD phải đúng 12 chữ số';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitError('');
    if (!validateForm()) return;
    try {
      const data = await apiFetch('/api/auth/recover-password', {
        method: 'POST',
        skipAuth: true,
        body: JSON.stringify({
          username: username.trim(),
          cccd: String(cccd).replace(/\D/g, ''),
        }),
      });
      setResult(data);
    } catch (err) {
      setSubmitError(err.message || 'Không thực hiện được');
    }
  };

  if (result) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center px-4">
        <div className="max-w-md w-full">
          <div className="text-center mb-8">
            <div className="flex justify-center mb-4">
              <div className="bg-green-600 p-3 rounded-2xl shadow-lg shadow-green-500/50">
                <CheckCircle className="h-12 w-12 text-white" />
              </div>
            </div>
            <h1 className="text-2xl font-bold text-white mb-2">Xác thực thành công</h1>
            <p className="text-slate-400 text-sm text-left mb-4">{result.message}</p>
            <div className="bg-slate-800 rounded-xl p-4 border border-slate-600 text-left">
              <p className="text-slate-400 text-xs mb-1">Mật khẩu tạm thời mới (đăng nhập rồi đổi mật khẩu):</p>
              <p className="text-green-400 font-mono text-lg font-bold break-all">{result.temporary_password}</p>
            </div>
          </div>
          <Link
            to="/login"
            className="block w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg text-center"
          >
            Về đăng nhập
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <div className="bg-blue-600 p-3 rounded-2xl shadow-lg shadow-blue-500/50">
              <Cpu className="h-12 w-12 text-white" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Lấy lại mật khẩu</h1>
          <p className="text-slate-400">Nhập đúng tên đăng nhập và CCCD</p>
        </div>

        <div className="bg-slate-800 rounded-2xl shadow-xl p-8 border border-slate-700">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Tên đăng nhập</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <User className="h-5 w-5 text-slate-400" />
                </div>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className={`w-full pl-10 pr-4 py-3 bg-slate-700 border ${
                    errors.username ? 'border-red-500' : 'border-slate-600'
                  } rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500`}
                  placeholder="username"
                />
              </div>
              {errors.username && (
                <div className="flex items-center mt-2 text-red-400 text-sm">
                  <AlertCircle className="h-4 w-4 mr-1" />
                  {errors.username}
                </div>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">CCCD (12 số)</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Hash className="h-5 w-5 text-slate-400" />
                </div>
                <input
                  type="text"
                  inputMode="numeric"
                  value={cccd}
                  onChange={(e) => setCccd(e.target.value.replace(/\D/g, '').slice(0, 12))}
                  className={`w-full pl-10 pr-4 py-3 bg-slate-700 border ${
                    errors.cccd ? 'border-red-500' : 'border-slate-600'
                  } rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500`}
                  placeholder="012345678901"
                />
              </div>
              {errors.cccd && (
                <div className="flex items-center mt-2 text-red-400 text-sm">
                  <AlertCircle className="h-4 w-4 mr-1" />
                  {errors.cccd}
                </div>
              )}
            </div>

            {submitError && (
              <div className="p-3 rounded-lg bg-red-900/40 border border-red-700 text-red-200 text-sm">{submitError}</div>
            )}

            <button
              type="submit"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg transition-all duration-200"
            >
              Xác nhận
            </button>
          </form>

          <div className="mt-6 text-center">
            <Link to="/login" className="text-blue-400 hover:text-blue-300 font-medium">
              ← Về đăng nhập
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ForgotPassword;
