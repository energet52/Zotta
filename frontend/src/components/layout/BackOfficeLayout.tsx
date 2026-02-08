import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import { LayoutDashboard, ClipboardList, BarChart3, Settings, LogOut } from 'lucide-react';
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
    { to: '/backoffice/queue', icon: ClipboardList, label: 'Queue' },
    { to: '/backoffice/reports', icon: BarChart3, label: 'Reports' },
  ];

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-[var(--color-primary-dark)] text-white hidden md:flex flex-col">
        <div className="p-4 border-b border-white/10">
          <Link to="/backoffice" className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-[var(--color-accent)] rounded-lg flex items-center justify-center font-bold text-lg">
              Z
            </div>
            <div>
              <div className="font-bold">Zotta</div>
              <div className="text-xs text-white/60">Back Office</div>
            </div>
          </Link>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <Link
              key={to}
              to={to}
              className={clsx(
                'flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm transition-colors',
                location.pathname === to
                  ? 'bg-white/15 text-white'
                  : 'text-white/60 hover:text-white hover:bg-white/10'
              )}
            >
              <Icon size={18} />
              <span>{label}</span>
            </Link>
          ))}
        </nav>

        <div className="p-4 border-t border-white/10">
          <div className="flex items-center justify-between">
            <div className="text-sm">
              <div className="font-medium">{user?.first_name} {user?.last_name}</div>
              <div className="text-xs text-white/50 capitalize">{user?.role?.replace('_', ' ')}</div>
            </div>
            <button onClick={handleLogout} className="p-2 hover:bg-white/10 rounded-lg" title="Logout">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col">
        {/* Mobile header */}
        <header className="md:hidden bg-[var(--color-primary-dark)] text-white p-4 flex items-center justify-between">
          <span className="font-bold">Zotta Back Office</span>
          <button onClick={handleLogout}>
            <LogOut size={18} />
          </button>
        </header>

        {/* Mobile nav */}
        <nav className="md:hidden bg-white border-b px-4 py-2 flex space-x-2 overflow-x-auto">
          {navItems.map(({ to, icon: Icon, label }) => (
            <Link
              key={to}
              to={to}
              className={clsx(
                'flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs whitespace-nowrap',
                location.pathname === to
                  ? 'bg-[var(--color-primary)] text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              )}
            >
              <Icon size={14} />
              <span>{label}</span>
            </Link>
          ))}
        </nav>

        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
