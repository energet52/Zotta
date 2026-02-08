import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import { Home, FileText, Upload, User, LogOut } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { clsx } from 'clsx';

export default function ConsumerLayout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { to: '/dashboard', icon: Home, label: 'Dashboard' },
    { to: '/apply', icon: FileText, label: 'Apply' },
    { to: '/applications', icon: Upload, label: 'My Applications' },
    { to: '/profile', icon: User, label: 'Profile' },
  ];

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      {/* Header */}
      <header className="bg-[var(--color-primary)] text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link to="/dashboard" className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-[var(--color-accent)] rounded-lg flex items-center justify-center font-bold text-lg">
                Z
              </div>
              <span className="text-xl font-bold">Zotta</span>
            </Link>
            <nav className="hidden md:flex items-center space-x-1">
              {navItems.map(({ to, icon: Icon, label }) => (
                <Link
                  key={to}
                  to={to}
                  className={clsx(
                    'flex items-center space-x-1.5 px-3 py-2 rounded-lg text-sm transition-colors',
                    location.pathname === to
                      ? 'bg-white/20 text-white'
                      : 'text-white/70 hover:text-white hover:bg-white/10'
                  )}
                >
                  <Icon size={16} />
                  <span>{label}</span>
                </Link>
              ))}
            </nav>
            <div className="flex items-center space-x-3">
              <span className="text-sm text-white/80">
                {user?.first_name} {user?.last_name}
              </span>
              <button onClick={handleLogout} className="p-2 hover:bg-white/10 rounded-lg transition-colors" title="Logout">
                <LogOut size={18} />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Mobile nav */}
      <nav className="md:hidden bg-white border-b border-gray-200 px-4 py-2 flex space-x-1 overflow-x-auto">
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

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  );
}
