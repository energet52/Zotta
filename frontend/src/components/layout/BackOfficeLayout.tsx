import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import { LayoutDashboard, ClipboardList, BarChart3, LogOut, Shield, BookOpen, AlertTriangle, PlusCircle, CreditCard } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { clsx } from 'clsx';

export default function BackOfficeLayout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { to: '/backoffice', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/backoffice/applications', icon: ClipboardList, label: 'Applications' },
    { to: '/backoffice/loans', icon: BookOpen, label: 'Loan Book' },
    { to: '/backoffice/collections', icon: AlertTriangle, label: 'Collections' },
    { to: '/backoffice/new-application', icon: PlusCircle, label: 'New Application' },
    { to: '/backoffice/reports', icon: BarChart3, label: 'Reports' },
  ];

  return (
    <div className="theme-dark min-h-screen bg-[var(--color-bg)] text-[var(--color-text)] flex">
      {/* Sidebar */}
      <aside className="w-64 bg-[var(--color-surface)] border-r border-[var(--color-border)] hidden md:flex flex-col">
        <div className="p-4 border-b border-[var(--color-border)]">
          <Link to="/backoffice" className="flex items-center space-x-3">
            <div className="w-9 h-9 bg-gradient-to-br from-sky-400 to-cyan-300 rounded-lg flex items-center justify-center font-bold text-lg text-[#0a1628]">
              Z
            </div>
            <div>
              <div className="font-bold text-[var(--color-text)]">Zotta</div>
              <div className="text-xs text-[var(--color-text-muted)]">Back Office</div>
            </div>
          </Link>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => {
            const isActive = to === '/backoffice'
              ? location.pathname === '/backoffice'
              : location.pathname.startsWith(to);
            return (
              <Link
                key={to}
                to={to}
                className={clsx(
                  'flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm transition-all',
                  isActive
                    ? 'bg-[var(--color-primary)]/15 text-[var(--color-primary)] font-medium'
                    : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]'
                )}
              >
                <Icon size={18} />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-[var(--color-border)]">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 rounded-full bg-[var(--color-primary)]/20 flex items-center justify-center">
                <Shield size={14} className="text-[var(--color-primary)]" />
              </div>
              <div className="text-sm">
                <div className="font-medium text-[var(--color-text)]">{user?.first_name} {user?.last_name}</div>
                <div className="text-xs text-[var(--color-text-muted)] capitalize">{user?.role?.replace('_', ' ')}</div>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="p-2 hover:bg-[var(--color-surface-hover)] rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-danger)] transition-colors"
              title="Logout"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col">
        {/* Mobile header */}
        <header className="md:hidden bg-[var(--color-surface)] border-b border-[var(--color-border)] text-[var(--color-text)] p-4 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-7 h-7 bg-gradient-to-br from-sky-400 to-cyan-300 rounded-lg flex items-center justify-center font-bold text-sm text-[#0a1628]">
              Z
            </div>
            <span className="font-bold">Zotta</span>
          </div>
          <button onClick={handleLogout} className="text-[var(--color-text-muted)]">
            <LogOut size={18} />
          </button>
        </header>

        {/* Mobile nav */}
        <nav className="md:hidden bg-[var(--color-surface)] border-b border-[var(--color-border)] px-4 py-2 flex space-x-2 overflow-x-auto">
          {navItems.map(({ to, icon: Icon, label }) => {
            const isActive = to === '/backoffice'
              ? location.pathname === '/backoffice'
              : location.pathname.startsWith(to);
            return (
              <Link
                key={to}
                to={to}
                className={clsx(
                  'flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs whitespace-nowrap',
                  isActive
                    ? 'bg-[var(--color-primary)]/15 text-[var(--color-primary)]'
                    : 'text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]'
                )}
              >
                <Icon size={14} />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>

        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
