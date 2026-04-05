import React from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Home, LayoutDashboard, Cpu, Users, LogOut, KeyRound } from 'lucide-react';

const Layout = () => {
  const { logout, user, isAdmin } = useAuth();
  const location = useLocation();

  const navItems = [
    { to: '/home', label: 'Home', icon: Home },
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/devices', label: 'Devices', icon: Cpu },
  ];

  if (isAdmin()) {
    navItems.push({ to: '/user-management', label: 'Quản lý người dùng', icon: Users });
  }
  navItems.push({ to: '/change-password', label: 'Đổi mật khẩu', icon: KeyRound });

  const isNavItemActive = (to) => {
    const path = location.pathname;
    if (to === '/devices') return path === '/devices' || path.startsWith('/devices/');
    return path === to;
  };

  return (
    <div className="min-h-screen bg-slate-900">
      {/* Top Navigation Bar */}
      <nav className="bg-slate-800 border-b border-slate-700 shadow-lg sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo and Brand */}
            <div className="flex items-center space-x-2">
              <Cpu className="h-8 w-8 text-blue-500" />
              <span className="text-xl font-bold text-white">IoT Management</span>
            </div>

            {/* Navigation Links */}
            <div className="hidden md:flex items-center space-x-1">
              {navItems.map((item) => (
                <NavLink
                  key={`${item.to}-${item.label}`}
                  to={item.to}
                  className={() => {
                    const active = isNavItemActive(item.to);
                    return `flex items-center space-x-2 px-4 py-2 rounded-lg transition-all duration-200 ${
                      active
                        ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/50'
                        : 'text-slate-300 hover:bg-slate-700 hover:text-white'
                    }`;
                  }}
                >
                  <item.icon className="h-5 w-5" />
                  <span className="font-medium">{item.label}</span>
                </NavLink>
              ))}
            </div>

            {/* User Info and Logout */}
            <div className="flex items-center space-x-4">
              <div className="text-right hidden sm:block">
                <p className="text-sm text-slate-300">{user?.fullname ?? user?.username}</p>
                <p className="text-xs text-slate-400">{user?.role}</p>
              </div>
              <button
                onClick={logout}
                className="flex items-center space-x-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors duration-200"
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden sm:inline">Logout</span>
              </button>
            </div>
          </div>

          {/* Mobile Navigation */}
          <div className="md:hidden flex justify-around pb-3 space-x-2">
            {navItems.map((item) => (
              <NavLink
                key={`${item.to}-${item.label}`}
                to={item.to}
                className={() => {
                  const active = isNavItemActive(item.to);
                  return `flex flex-col items-center space-y-1 px-3 py-2 rounded-lg transition-all duration-200 ${
                    active ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-700'
                  }`;
                }}
              >
                <item.icon className="h-5 w-5" />
                <span className="text-xs">{item.label}</span>
              </NavLink>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
