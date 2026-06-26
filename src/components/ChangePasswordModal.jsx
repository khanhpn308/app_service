import React, { useState } from 'react';
import { Lock, AlertCircle, CheckCircle } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './ui/dialog';
import { Button } from './ui/button';

/**
 * Modal đổi mật khẩu thiết bị (hiện là MOCK — chưa gọi API).
 * Dùng <Dialog> shadcn để có focus-trap, đóng bằng ESC/overlay, aria chuẩn.
 *
 * Component được render có điều kiện ở parent (`{open && <ChangePasswordModal/>}`),
 * nên Dialog luôn mở khi mount; đóng (ESC/overlay/Cancel) gọi `onClose`.
 */
const ChangePasswordModal = ({ deviceId, onClose }) => {
  const [formData, setFormData] = useState({
    oldPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  const [errors, setErrors] = useState({});
  const [success, setSuccess] = useState(false);

  const validateForm = () => {
    const newErrors = {};

    if (!formData.oldPassword) {
      newErrors.oldPassword = 'Current password is required';
    }

    if (!formData.newPassword) {
      newErrors.newPassword = 'New password is required';
    } else if (formData.newPassword.length < 6) {
      newErrors.newPassword = 'Password must be at least 6 characters';
    }

    if (!formData.confirmPassword) {
      newErrors.confirmPassword = 'Please confirm your password';
    } else if (formData.newPassword !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }

    if (formData.oldPassword && formData.newPassword && formData.oldPassword === formData.newPassword) {
      newErrors.newPassword = 'New password must be different from current password';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (validateForm()) {
      // Mock password change
      setSuccess(true);
      setTimeout(() => {
        onClose();
      }, 2000);
    }
  };

  // Đóng dialog khi không phải trạng thái success (success tự đóng sau timeout).
  const handleOpenChange = (open) => {
    if (!open && !success) onClose();
  };

  const inputClass = (hasError) =>
    `w-full px-4 py-3 bg-background border ${
      hasError ? 'border-red-500' : 'border-border'
    } rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all duration-200`;

  return (
    <Dialog open onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        {success ? (
          <div className="py-4 text-center">
            <div className="flex justify-center mb-4">
              <div className="p-3 bg-green-500/20 rounded-full">
                <CheckCircle className="h-12 w-12 text-green-500" />
              </div>
            </div>
            <DialogTitle className="text-xl mb-2">Password Changed!</DialogTitle>
            <DialogDescription>
              Password for device{' '}
              <span className="text-primary font-mono">{deviceId}</span>{' '}
              has been successfully updated.
            </DialogDescription>
          </div>
        ) : (
          <>
            <DialogHeader>
              <div className="flex items-center space-x-3">
                <div className="p-2 bg-blue-500/20 rounded-lg">
                  <Lock className="h-6 w-6 text-primary" />
                </div>
                <DialogTitle className="text-xl">Change Password</DialogTitle>
              </div>
              <DialogDescription className="sr-only">
                Đổi mật khẩu cho thiết bị {deviceId}
              </DialogDescription>
            </DialogHeader>

            {/* Device ID Display */}
            <div className="bg-background rounded-lg p-4 border border-border">
              <p className="text-muted-foreground text-sm mb-1">Device ID</p>
              <p className="text-primary font-mono font-semibold">{deviceId}</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label htmlFor="oldPassword" className="block text-sm font-medium text-foreground/90 mb-2">
                  Current Password *
                </label>
                <input
                  id="oldPassword"
                  type="password"
                  name="oldPassword"
                  value={formData.oldPassword}
                  onChange={handleChange}
                  className={inputClass(errors.oldPassword)}
                  placeholder="Enter current password"
                />
                {errors.oldPassword && (
                  <div className="flex items-center mt-2 text-red-400 text-sm">
                    <AlertCircle className="h-4 w-4 mr-1" />
                    {errors.oldPassword}
                  </div>
                )}
              </div>

              <div>
                <label htmlFor="newPassword" className="block text-sm font-medium text-foreground/90 mb-2">
                  New Password *
                </label>
                <input
                  id="newPassword"
                  type="password"
                  name="newPassword"
                  value={formData.newPassword}
                  onChange={handleChange}
                  className={inputClass(errors.newPassword)}
                  placeholder="Enter new password"
                />
                {errors.newPassword && (
                  <div className="flex items-center mt-2 text-red-400 text-sm">
                    <AlertCircle className="h-4 w-4 mr-1" />
                    {errors.newPassword}
                  </div>
                )}
              </div>

              <div>
                <label htmlFor="confirmPassword" className="block text-sm font-medium text-foreground/90 mb-2">
                  Confirm New Password *
                </label>
                <input
                  id="confirmPassword"
                  type="password"
                  name="confirmPassword"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  className={inputClass(errors.confirmPassword)}
                  placeholder="Confirm new password"
                />
                {errors.confirmPassword && (
                  <div className="flex items-center mt-2 text-red-400 text-sm">
                    <AlertCircle className="h-4 w-4 mr-1" />
                    {errors.confirmPassword}
                  </div>
                )}
              </div>

              <DialogFooter>
                <Button type="button" variant="outline" onClick={onClose} className="flex-1">
                  Cancel
                </Button>
                <Button type="submit" className="flex-1">
                  Change Password
                </Button>
              </DialogFooter>
            </form>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default ChangePasswordModal;
