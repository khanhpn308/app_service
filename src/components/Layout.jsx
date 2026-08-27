/**
 * Khung UI sau đăng nhập: thanh nav (desktop + mobile), nút logout, `<Outlet />` cho nội dung trang.
 *
 * - Nav items: Home, Dashboard, Devices; thêm User Management nếu `isAdmin()`.
 * - `isNavItemActive`: highlight `/devices` khi đang ở `/devices/:id`.
 */
import React from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Activity, Home, LayoutDashboard, Cpu, Users, LogOut, KeyRound, RadioTower, Menu } from 'lucide-react';

const Layout = () => {
  const { logout, user, isAdmin } = useAuth();
  const location = useLocation();
  const isGpsDashboard = location.pathname === '/dashboard/gps';

  const navItems = [
    { to: '/home', label: 'Home', icon: Home },
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, hasSubmenu: true },
    { to: '/devices', label: 'Devices', icon: Cpu },
  ];

  if (isAdmin()) {
    navItems.push({ to: '/user-management', label: 'Quản lý người dùng', icon: Users });
    navItems.push({ to: '/topic-management', label: 'Quản lý topic', icon: RadioTower });
    navItems.push({ to: '/ping', label: 'Ping', icon: Activity });
  }
  navItems.push({ to: '/change-password', label: 'Đổi mật khẩu', icon: KeyRound });

  const isNavItemActive = (to) => {
    const path = location.pathname;
    if (to === '/devices') return path === '/devices' || path.startsWith('/devices/');
    return path === to;
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Top Navigation Bar */}
      <nav className="bg-card border-b border-border shadow-lg sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo and Brand */}
            <div className="flex items-center space-x-2">
              <Cpu className="h-8 w-8 text-primary" />
              <span className="text-xl font-bold text-foreground">IoT Management</span>
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
                        ? 'bg-primary text-foreground shadow-lg shadow-blue-500/50'
                        : 'text-foreground/90 hover:bg-card hover:text-foreground'
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
                <p className="text-sm text-foreground/90">{user?.fullname ?? user?.username}</p>
                <p className="text-xs text-muted-foreground">{user?.role}</p>
              </div>
              <button
                onClick={logout}
                className="flex items-center space-x-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-foreground rounded-lg transition-colors duration-200"
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden sm:inline">Logout</span>
              </button>
            </div>
          </div>

          {/* Mobile Navigation */}
          <div className="md:hidden flex gap-2 overflow-x-auto pb-3">
            {navItems.map((item) => (
              <NavLink
                key={`${item.to}-${item.label}`}
                to={item.to}
                className={() => {
                  const active = isNavItemActive(item.to);
                  return `flex min-w-fit shrink-0 flex-col items-center space-y-1 px-3 py-2 rounded-lg transition-all duration-200 ${
                    active ? 'bg-primary text-foreground' : 'text-foreground/90 hover:bg-card'
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

      {/* Dashboard Sub-navigation (Hamburger Switcher) */}
      {location.pathname.startsWith('/dashboard') && (
        <div className="border-b border-border bg-card px-4 sm:px-6 lg:px-8">
          <div className="flex min-h-14 w-full items-center gap-3 overflow-x-auto">
            <div className="flex shrink-0 items-center gap-2 pr-2 text-foreground/90">
              <Menu className="h-5 w-5" />
              <span className="text-sm font-medium">Dashboard Menu</span>
            </div>
              <nav
                id="dashboard-subnavigation"
                aria-label="Điều hướng Dashboard"
                className="flex flex-row items-center gap-1"
              >
                <NavLink
                  to="/dashboard"
                  end
                  className={({ isActive }) => `min-h-11 rounded-md px-3 py-3 text-sm font-medium transition-colors ${isActive ? 'bg-primary text-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'}`}
                >
                  Telemetry
                </NavLink>
                <NavLink
                  to="/dashboard/gps"
                  className={({ isActive }) => `min-h-11 whitespace-nowrap rounded-md px-3 py-3 text-sm font-medium transition-colors ${isActive ? 'bg-primary text-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'}`}
                >
                  Asset &amp; worker Tracking
                </NavLink>
              </nav>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className={isGpsDashboard
        ? 'w-full max-w-none p-0'
        : 'max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8'}>
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
