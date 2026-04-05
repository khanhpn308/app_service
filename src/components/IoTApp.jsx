import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from '../contexts/AuthContext';
import Layout from './Layout';
import Login from '../pages/Login';
import ForgotPassword from '../pages/ForgotPassword';
import Home from '../pages/Home';
import GlobalDashboard from '../pages/GlobalDashboard';
import Devices from '../pages/Devices';
import DeviceDetail from '../pages/DeviceDetail';
import UserManagement from '../pages/UserManagement';
import ChangePassword from '../pages/ChangePassword';
import ProtectedRoute from './ProtectedRoute';
import AdminRoute from './AdminRoute';

function IoTApp() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />

          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/" element={<Navigate to="/home" replace />} />
              <Route path="/home" element={<Home />} />
              <Route path="/dashboard" element={<GlobalDashboard />} />
              <Route path="/change-password" element={<ChangePassword />} />
              <Route path="/devices" element={<Devices />} />
              <Route path="/devices/:deviceId" element={<DeviceDetail />} />
              <Route element={<AdminRoute />}>
                <Route path="/user-management" element={<UserManagement />} />
              </Route>
            </Route>
          </Route>
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default IoTApp;
