import { useEffect } from 'react';
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import { Home, FileText, Upload, User, LogOut, Wallet, Bell, MessageCircle, Sparkles } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { useNotificationStore } from '../../store/notificationStore';
import { clsx } from 'clsx';

export default function ConsumerLayout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const { unreadCount, startPolling, stopPolling } = useNotificationStore();

  useEffect(() => {
    startPolling();
    return () => stopPolling();
  }, []);

  const handleLogout = () => {
    stopPolling();
    logout();
    navigate('/login');
  };

  const navItems = [
    { to: '/dashboard', icon: Home, label: 'Dashboard' },
    { to: '/pre-approval', icon: Sparkles, label: 'Quick Check' },
    { to: '/chat', icon: MessageCircle, label: 'Chat' },
    { to: '/apply', icon: FileText, label: 'Apply' },
    { to: '/loans', icon: Wallet, label: 'My Loans' },
    { to: '/applications', icon: Upload, label: 'My Applications' },
    { to: '/profile', icon: User, label: 'Profile' },
  ];

  return (
    <div className="theme-consumer min-h-screen bg-[var(--color-bg)] responsive-shell">
      {/* Header */}
      <header className="bg-[var(--color-surface)] border-b border-[var(--color-border)]">
        <div className="max-w-7xl mx-auto px-4 sm:px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link to="/dashboard" className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-[var(--color-primary)] rounded-lg flex items-center justify-center font-bold text-lg text-white">
                Z
              </div>
              <span className="text-xl font-bold text-[var(--color-text)]">Zotta</span>
            </Link>
            <nav className="hidden md:flex items-center space-x-1">
              {navItems.map(({ to, icon: Icon, label }) => (
                <Link
                  key={to}
                  to={to}
                  className={clsx(
                    'flex items-center space-x-1.5 px-3 py-2 rounded-lg text-sm transition-colors',
                    location.pathname === to
                      ? 'bg-[var(--color-primary)]/20 text-[var(--color-primary)]'
                      : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]'
                  )}
                >
                  <Icon size={16} />
                  <span>{label}</span>
                </Link>
              ))}
            </nav>
            <div className="flex items-center space-x-3">
              {/* Notification Bell */}
              <Link
                to="/notifications"
                className={clsx(
                  'relative p-2 rounded-lg transition-colors',
                  location.pathname === '/notifications'
                    ? 'bg-[var(--color-primary)]/20 text-[var(--color-primary)]'
                    : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]'
                )}
                title="Notifications"
              >
                <Bell size={18} />
                {unreadCount > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-red-500 text-white text-[10px] font-bold px-1 leading-none">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                )}
              </Link>
              <span className="hidden sm:inline text-sm text-[var(--color-text-muted)]">
                {user?.first_name} {user?.last_name}
              </span>
              <button onClick={handleLogout} className="p-2 hover:bg-[var(--color-surface-hover)] rounded-lg transition-colors text-[var(--color-text-muted)] hover:text-[var(--color-text)]" title="Logout">
                <LogOut size={18} />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Mobile nav */}
      <nav className="md:hidden bg-[var(--color-surface)] border-b border-[var(--color-border)] px-4 py-2 flex space-x-1 overflow-x-auto max-w-full">
        {navItems.map(({ to, icon: Icon, label }) => (
          <Link
            key={to}
            to={to}
            className={clsx(
              'flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs whitespace-nowrap transition-colors',
              location.pathname === to
                ? 'bg-[var(--color-primary)] text-white'
                : 'text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text)]'
            )}
          >
            <Icon size={14} />
            <span>{label}</span>
          </Link>
        ))}
        <Link
          to="/notifications"
          className={clsx(
            'flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs whitespace-nowrap transition-colors relative',
            location.pathname === '/notifications'
              ? 'bg-[var(--color-primary)] text-white'
              : 'text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text)]'
          )}
        >
          <Bell size={14} />
          <span>Notifications</span>
          {unreadCount > 0 && (
            <span className="ml-1 min-w-[16px] h-[16px] flex items-center justify-center rounded-full bg-red-500 text-white text-[9px] font-bold px-0.5 leading-none">
              {unreadCount > 99 ? '99+' : unreadCount}
            </span>
          )}
        </Link>
      </nav>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-4 sm:px-6 lg:px-8 py-4 sm:py-4 sm:py-6 lg:py-8">
        <Outlet />
      </main>
    </div>
  );
}
