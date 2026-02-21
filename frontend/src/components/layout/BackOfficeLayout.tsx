import { useState, useEffect, useMemo, useCallback } from 'react';
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  BarChart3,
  LogOut,
  Shield,
  BookOpen,
  AlertTriangle,
  PlusCircle,
  Boxes,
  Store,
  Scale,
  MessageCircle,
  Landmark,
  FileText,
  BookOpenCheck,
  CalendarDays,
  BarChart,
  GitBranch,
  TrendingUp,
  FileBarChart,
  Wrench,
  ShieldAlert,
  MessageSquare,
  Users,
  ScrollText,
  PieChart,
  Target,
  ChevronRight,
  Menu,
  Search,
  X,
  Zap,
  Inbox,
  Settings,
  type LucideIcon,
} from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { clsx } from 'clsx';

/* ── Types ──────────────────────────────────────────────────────── */

interface NavItem {
  to: string;
  icon: LucideIcon;
  label: string;
}

interface NavSection {
  id: string;
  label: string;
  icon: LucideIcon;
  items: NavItem[];
  adminOnly?: boolean;
}

/* ── Section definitions ────────────────────────────────────────── */

const SECTIONS: NavSection[] = [
  {
    id: 'lending',
    label: 'Lending',
    icon: BookOpen,
    items: [
      { to: '/backoffice/conversations', icon: MessageCircle, label: 'Conversations' },
      { to: '/backoffice/new-application', icon: PlusCircle, label: 'New Application' },
      { to: '/backoffice/loans', icon: BookOpen, label: 'Loan Book' },
      { to: '/backoffice/customers', icon: Users, label: 'Customers' },
    ],
  },
  {
    id: 'applications',
    label: 'Applications',
    icon: Inbox,
    items: [
      { to: '/backoffice/queue', icon: Inbox, label: 'Applications Queue' },
      { to: '/backoffice/queue/config', icon: Settings, label: 'Configuration' },
      { to: '/backoffice/queue/analytics', icon: BarChart3, label: 'Analytics' },
    ],
  },
  {
    id: 'pre-approvals',
    label: 'Pre-Approvals',
    icon: Shield,
    items: [
      { to: '/backoffice/pre-approvals', icon: Shield, label: 'Dashboard & Referred' },
    ],
  },
  {
    id: 'collections',
    label: 'Collections',
    icon: AlertTriangle,
    items: [
      { to: '/backoffice/collections', icon: AlertTriangle, label: 'Queue' },
      { to: '/backoffice/collections-dashboard', icon: BarChart3, label: 'Analytics' },
      { to: '/backoffice/collection-sequences', icon: Zap, label: 'Sequences' },
    ],
  },
  {
    id: 'scoring',
    label: 'Decisioning',
    icon: Target,
    items: [
      { to: '/backoffice/strategies', icon: Shield, label: 'Strategies' },
      { to: '/backoffice/strategy-audit', icon: ScrollText, label: 'Strategy Audit Log' },
      { to: '/backoffice/champion-challenger', icon: Zap, label: 'Champion-Challenger' },
      { to: '/backoffice/scorecards', icon: Target, label: 'Scorecards' },
    ],
  },
  {
    id: 'sector',
    label: 'Sector Analysis',
    icon: PieChart,
    items: [
      { to: '/backoffice/sector-analysis', icon: PieChart, label: 'Concentration' },
      { to: '/backoffice/sector-analysis/policies', icon: Target, label: 'Policies & Alerts' },
    ],
  },
  {
    id: 'gl',
    label: 'General Ledger',
    icon: Landmark,
    items: [
      { to: '/backoffice/gl', icon: LayoutDashboard, label: 'Dashboard' },
      { to: '/backoffice/gl/anomalies', icon: ShieldAlert, label: 'Anomalies' },
      { to: '/backoffice/gl/chat', icon: MessageSquare, label: 'GL Chat' },
      { to: '/backoffice/gl/accounts', icon: Landmark, label: 'Chart of Accounts' },
      { to: '/backoffice/gl/entries', icon: FileText, label: 'Journal Entries' },
      { to: '/backoffice/gl/ledger', icon: BookOpenCheck, label: 'Account Ledger' },
      { to: '/backoffice/gl/trial-balance', icon: BarChart, label: 'Trial Balance' },
      { to: '/backoffice/gl/balance-sheet', icon: Scale, label: 'Balance Sheet' },
      { to: '/backoffice/gl/income-statement', icon: TrendingUp, label: 'Income Statement' },
      { to: '/backoffice/gl/periods', icon: CalendarDays, label: 'Periods' },
      { to: '/backoffice/gl/mappings', icon: GitBranch, label: 'GL Mappings' },
      { to: '/backoffice/gl/reports', icon: FileBarChart, label: 'Reports' },
      { to: '/backoffice/gl/report-builder', icon: Wrench, label: 'Report Builder' },
    ],
  },
  {
    id: 'reports',
    label: 'Reports',
    icon: BarChart3,
    items: [
      { to: '/backoffice/reports', icon: BarChart3, label: 'Reports' },
    ],
  },
  {
    id: 'users',
    label: 'User Management',
    icon: Users,
    adminOnly: true,
    items: [
      { to: '/backoffice/users', icon: Users, label: 'Users' },
      { to: '/backoffice/users/roles', icon: Shield, label: 'Roles & Permissions' },
    ],
  },
  {
    id: 'admin',
    label: 'Administration',
    icon: Shield,
    adminOnly: true,
    items: [
      { to: '/backoffice/products', icon: Boxes, label: 'Products' },
      { to: '/backoffice/merchants', icon: Store, label: 'Merchants' },
      { to: '/backoffice/rules', icon: Scale, label: 'Rules' },
      { to: '/backoffice/audit-trail', icon: ScrollText, label: 'Audit Trail' },
      { to: '/backoffice/error-monitor', icon: ShieldAlert, label: 'Error Monitor' },
    ],
  },
];

const STORAGE_KEY = 'zotta-nav-collapsed';

function loadCollapsed(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveCollapsed(state: Record<string, boolean>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch { /* ignore */ }
}

/* ── Active-path helpers ────────────────────────────────────────── */

function isItemActive(to: string, pathname: string): boolean {
  if (to === '/backoffice') return pathname === '/backoffice';
  if (to === '/backoffice/gl') return pathname === '/backoffice/gl';
  if (to === '/backoffice/sector-analysis') return pathname === '/backoffice/sector-analysis';
  return pathname.startsWith(to);
}

function isSectionActive(section: NavSection, pathname: string): boolean {
  return section.items.some(item => isItemActive(item.to, pathname));
}

/* ── Component ──────────────────────────────────────────────────── */

export default function BackOfficeLayout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const isAdmin = user?.role === 'admin';

  const [collapsed, setCollapsed] = useState<Record<string, boolean>>(loadCollapsed);
  const [search, setSearch] = useState('');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = () => { logout(); navigate('/login'); };

  const toggleSection = useCallback((id: string) => {
    setCollapsed(prev => {
      const next = { ...prev, [id]: !prev[id] };
      saveCollapsed(next);
      return next;
    });
  }, []);

  // Auto-expand section containing active route
  useEffect(() => {
    const activeSectionId = SECTIONS.find(s => isSectionActive(s, location.pathname))?.id;
    if (activeSectionId && collapsed[activeSectionId]) {
      setCollapsed(prev => {
        const next = { ...prev, [activeSectionId]: false };
        saveCollapsed(next);
        return next;
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  // Filter sections & items by search
  const filteredSections = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return SECTIONS;

    return SECTIONS.map(section => {
      const matchingItems = section.items.filter(item =>
        item.label.toLowerCase().includes(q) ||
        section.label.toLowerCase().includes(q)
      );
      if (matchingItems.length === 0) return null;
      return { ...section, items: matchingItems };
    }).filter(Boolean) as NavSection[];
  }, [search]);

  const isSearching = search.trim().length > 0;

  // The pinned dashboard link
  const dashboardActive = location.pathname === '/backoffice';

  const visibleSections = filteredSections.filter(s => !s.adminOnly || isAdmin);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  }, [mobileMenuOpen]);

  return (
    <div className="theme-dark min-h-screen bg-[var(--color-bg)] text-[var(--color-text)] flex responsive-shell">
      {/* ═══ Sidebar ═══ */}
      <aside className="w-64 bg-[var(--color-surface)] border-r border-[var(--color-border)] hidden md:flex flex-col">
        {/* Logo */}
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

        {/* Search */}
        <div className="px-3 pt-3 pb-1">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] pointer-events-none" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search menu..."
              className="w-full h-8 pl-8 pr-7 text-xs rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]/50 transition-shadow"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              >
                <X size={12} />
              </button>
            )}
          </div>
        </div>

        {/* Scrollable nav */}
        <nav className="flex-1 overflow-y-auto px-3 pt-1 pb-3 space-y-0.5 scrollbar-thin">
          {/* Dashboard — always pinned at top */}
          {(!isSearching || 'dashboard'.includes(search.trim().toLowerCase())) && (
            <Link
              to="/backoffice"
              className={clsx(
                'flex items-center space-x-3 px-3 py-2 rounded-lg text-sm transition-all',
                dashboardActive
                  ? 'bg-[var(--color-primary)]/15 text-[var(--color-primary)] font-medium'
                  : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]'
              )}
            >
              <LayoutDashboard size={18} />
              <span>Dashboard</span>
            </Link>
          )}

          {/* Sections */}
          {visibleSections.map(section => {
            const sectionActive = isSectionActive(section, location.pathname);
            const isOpen = isSearching || !collapsed[section.id];
            const SectionIcon = section.icon;

            return (
              <div key={section.id} className="pt-1.5">
                {/* Section header */}
                <button
                  onClick={() => !isSearching && toggleSection(section.id)}
                  className={clsx(
                    'w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition-colors select-none',
                    sectionActive
                      ? 'text-[var(--color-primary)]'
                      : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
                  )}
                >
                  <SectionIcon size={13} className="shrink-0 opacity-60" />
                  <span className="flex-1 text-left">{section.label}</span>
                  {!isSearching && (
                    <ChevronRight
                      size={12}
                      className={clsx(
                        'shrink-0 opacity-50 transition-transform duration-200',
                        isOpen && 'rotate-90'
                      )}
                    />
                  )}
                </button>

                {/* Items */}
                <div
                  className={clsx(
                    'overflow-hidden transition-all duration-200',
                    isOpen ? 'max-h-[600px] opacity-100' : 'max-h-0 opacity-0',
                  )}
                >
                  <div className="space-y-0.5 pt-0.5">
                    {section.items.map(({ to, icon: Icon, label }) => {
                      const itemActive = isItemActive(to, location.pathname);
                      return (
                        <Link
                          key={to}
                          to={to}
                          className={clsx(
                            'flex items-center space-x-3 pl-7 pr-3 py-2 rounded-lg text-sm transition-all',
                            itemActive
                              ? 'bg-[var(--color-primary)]/15 text-[var(--color-primary)] font-medium'
                              : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]'
                          )}
                        >
                          <Icon size={16} />
                          <span>{label}</span>
                        </Link>
                      );
                    })}
                  </div>
                </div>
              </div>
            );
          })}

          {/* Empty state for search */}
          {isSearching && visibleSections.length === 0 && !('dashboard'.includes(search.trim().toLowerCase())) && (
            <div className="text-center py-4 sm:py-6 text-xs text-[var(--color-text-muted)]">
              No menu items match "<span className="text-[var(--color-text)]">{search}</span>"
            </div>
          )}
        </nav>

        {/* User footer */}
        <div className="p-4 border-t border-[var(--color-border)]">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 min-w-0">
              <div className="w-8 h-8 rounded-full bg-[var(--color-primary)]/20 flex items-center justify-center shrink-0">
                <Shield size={14} className="text-[var(--color-primary)]" />
              </div>
              <div className="min-w-0">
                <div className="font-medium text-sm text-[var(--color-text)] truncate">{user?.first_name} {user?.last_name}</div>
                <div className="text-xs text-[var(--color-text-muted)] capitalize truncate">{user?.role?.replace('_', ' ')}</div>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="p-2 hover:bg-[var(--color-surface-hover)] rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-danger)] transition-colors shrink-0"
              title="Logout"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* ═══ Main content ═══ */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile header */}
        <header className="md:hidden bg-[var(--color-surface)] border-b border-[var(--color-border)] text-[var(--color-text)] px-3 py-2.5 flex items-center justify-between">
          <button
            onClick={() => setMobileMenuOpen(true)}
            className="p-2 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
            aria-label="Open menu"
          >
            <Menu size={18} />
          </button>
          <div className="flex items-center space-x-2 min-w-0">
            <div className="w-7 h-7 bg-gradient-to-br from-sky-400 to-cyan-300 rounded-lg flex items-center justify-center font-bold text-sm text-[#0a1628]">
              Z
            </div>
            <span className="font-bold truncate">Zotta Back Office</span>
          </div>
          <button
            onClick={handleLogout}
            className="p-2 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
            aria-label="Logout"
          >
            <LogOut size={18} />
          </button>
        </header>

        {/* Mobile menu drawer */}
        {mobileMenuOpen && (
          <>
            <button
              className="md:hidden fixed inset-0 z-40 bg-black/50"
              onClick={() => setMobileMenuOpen(false)}
              aria-label="Close menu backdrop"
            />
            <aside className="md:hidden fixed inset-y-0 left-0 z-50 w-72 max-w-[85vw] bg-[var(--color-surface)] border-r border-[var(--color-border)] flex flex-col">
              <div className="p-4 border-b border-[var(--color-border)] flex items-center justify-between">
                <Link to="/backoffice" className="flex items-center space-x-3" onClick={() => setMobileMenuOpen(false)}>
                  <div className="w-8 h-8 bg-gradient-to-br from-sky-400 to-cyan-300 rounded-lg flex items-center justify-center font-bold text-sm text-[#0a1628]">
                    Z
                  </div>
                  <div>
                    <div className="font-bold text-[var(--color-text)]">Zotta</div>
                    <div className="text-xs text-[var(--color-text-muted)]">Back Office</div>
                  </div>
                </Link>
                <button
                  onClick={() => setMobileMenuOpen(false)}
                  className="p-2 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
                  aria-label="Close menu"
                >
                  <X size={16} />
                </button>
              </div>

              <div className="px-3 pt-3 pb-2">
                <div className="relative">
                  <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] pointer-events-none" />
                  <input
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    placeholder="Search menu..."
                    className="w-full h-8 pl-8 pr-7 text-xs rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]/50 transition-shadow"
                  />
                  {search && (
                    <button
                      onClick={() => setSearch('')}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              </div>

              <nav className="flex-1 overflow-y-auto px-3 pb-4 space-y-3">
                {(!isSearching || 'dashboard'.includes(search.trim().toLowerCase())) && (
                  <Link
                    to="/backoffice"
                    onClick={() => setMobileMenuOpen(false)}
                    className={clsx(
                      'flex items-center space-x-3 px-3 py-2 rounded-lg text-sm transition-all',
                      dashboardActive
                        ? 'bg-[var(--color-primary)]/15 text-[var(--color-primary)] font-medium'
                        : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]'
                    )}
                  >
                    <LayoutDashboard size={16} />
                    <span>Dashboard</span>
                  </Link>
                )}

                {visibleSections.map(section => (
                  <div key={`mobile-${section.id}`} className="space-y-1">
                    <div className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                      {section.label}
                    </div>
                    {section.items.map(({ to, icon: Icon, label }) => {
                      const itemActive = isItemActive(to, location.pathname);
                      return (
                        <Link
                          key={`mobile-${to}`}
                          to={to}
                          onClick={() => setMobileMenuOpen(false)}
                          className={clsx(
                            'flex items-center space-x-3 px-3 py-2 rounded-lg text-sm transition-all',
                            itemActive
                              ? 'bg-[var(--color-primary)]/15 text-[var(--color-primary)] font-medium'
                              : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]'
                          )}
                        >
                          <Icon size={16} />
                          <span>{label}</span>
                        </Link>
                      );
                    })}
                  </div>
                ))}

                {isSearching && visibleSections.length === 0 && !('dashboard'.includes(search.trim().toLowerCase())) && (
                  <div className="text-center py-4 text-xs text-[var(--color-text-muted)]">
                    No menu items match "<span className="text-[var(--color-text)]">{search}</span>"
                  </div>
                )}
              </nav>

              <div className="p-4 border-t border-[var(--color-border)] flex items-center justify-between">
                <div className="min-w-0">
                  <div className="font-medium text-sm text-[var(--color-text)] truncate">{user?.first_name} {user?.last_name}</div>
                  <div className="text-xs text-[var(--color-text-muted)] capitalize truncate">{user?.role?.replace('_', ' ')}</div>
                </div>
                <button
                  onClick={handleLogout}
                  className="p-2 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-danger)] hover:bg-[var(--color-surface-hover)] transition-colors"
                  title="Logout"
                >
                  <LogOut size={16} />
                </button>
              </div>
            </aside>
          </>
        )}

        <main className="flex-1 p-3 sm:p-4 md:p-6 overflow-y-auto overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
