import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Users, Plus, Search, Shield, ShieldAlert, ShieldOff,
  Lock, Unlock, ChevronDown, RefreshCw, MoreHorizontal,
  UserCheck, UserX, Eye, Clock,
} from 'lucide-react';
import { userApi } from '../../../api/endpoints';
import { clsx } from 'clsx';

interface UserRow {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  role: string;
  status: string;
  employee_id: string | null;
  department: string | null;
  job_title: string | null;
  mfa_enabled: boolean;
  last_login_at: string | null;
  is_active: boolean;
  created_at: string;
}

interface StatusCount {
  total: number;
  by_status: Record<string, number>;
}

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-emerald-500/15 text-emerald-400',
  suspended: 'bg-amber-500/15 text-amber-400',
  locked: 'bg-red-500/15 text-red-400',
  deactivated: 'bg-gray-500/15 text-gray-400',
  pending_activation: 'bg-sky-500/15 text-sky-400',
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  active: <UserCheck size={12} />,
  suspended: <ShieldOff size={12} />,
  locked: <Lock size={12} />,
  deactivated: <UserX size={12} />,
  pending_activation: <Clock size={12} />,
};

export default function UserManagement() {
  const navigate = useNavigate();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [counts, setCounts] = useState<StatusCount>({ total: 0, by_status: {} });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [actionMenuId, setActionMenuId] = useState<number | null>(null);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { limit: 100 };
      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      const [usersRes, countRes] = await Promise.all([
        userApi.list(params),
        userApi.count(),
      ]);
      setUsers(usersRes.data);
      setCounts(countRes.data);
    } catch (err) {
      console.error('Failed to load users', err);
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleAction = async (userId: number, action: string) => {
    try {
      if (action === 'suspend') await userApi.suspend(userId);
      else if (action === 'reactivate') await userApi.reactivate(userId);
      else if (action === 'deactivate') await userApi.deactivate(userId);
      else if (action === 'unlock') await userApi.unlock(userId);
      setActionMenuId(null);
      fetchUsers();
    } catch (err) {
      console.error('Action failed', err);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">User Management</h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            Manage users, roles, permissions, and access control
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/backoffice/users/roles"
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[var(--color-border)] text-sm text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
          >
            <Shield size={16} />
            Roles & Permissions
          </Link>
          <button
            onClick={() => navigate('/backoffice/users/new')}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white text-sm font-medium hover:opacity-90 transition-opacity"
          >
            <Plus size={16} />
            Create User
          </button>
        </div>
      </div>

      {/* Status cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {[
          { key: '', label: 'Total', count: counts.total, color: 'text-[var(--color-text)]', icon: <Users size={18} /> },
          { key: 'active', label: 'Active', count: counts.by_status.active || 0, color: 'text-emerald-400', icon: <UserCheck size={18} /> },
          { key: 'suspended', label: 'Suspended', count: counts.by_status.suspended || 0, color: 'text-amber-400', icon: <ShieldOff size={18} /> },
          { key: 'locked', label: 'Locked', count: counts.by_status.locked || 0, color: 'text-red-400', icon: <Lock size={18} /> },
          { key: 'deactivated', label: 'Deactivated', count: counts.by_status.deactivated || 0, color: 'text-gray-400', icon: <UserX size={18} /> },
        ].map(({ key, label, count, color, icon }) => (
          <button
            key={label}
            onClick={() => setStatusFilter(key)}
            className={clsx(
              'bg-[var(--color-surface)] border rounded-xl p-4 text-left transition-all hover:border-[var(--color-primary)]/50',
              statusFilter === key ? 'border-[var(--color-primary)]' : 'border-[var(--color-border)]',
            )}
          >
            <div className="flex items-center justify-between">
              <span className={clsx('opacity-60', color)}>{icon}</span>
              <span className={clsx('text-2xl font-bold', color)}>{count}</span>
            </div>
            <div className="text-xs text-[var(--color-text-muted)] mt-2">{label}</div>
          </button>
        ))}
      </div>

      {/* Search & filters */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by name, email, or employee ID..."
            className="w-full h-10 pl-10 pr-4 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]/50"
          />
        </div>
        <button
          onClick={fetchUsers}
          className="p-2 rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
          title="Refresh"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Table */}
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                <th className="text-left px-4 py-3 font-medium">User</th>
                <th className="text-left px-4 py-3 font-medium">Role</th>
                <th className="text-left px-4 py-3 font-medium">Department</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">MFA</th>
                <th className="text-left px-4 py-3 font-medium">Last Login</th>
                <th className="text-right px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-[var(--color-text-muted)]">
                    Loading users...
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-[var(--color-text-muted)]">
                    No users found
                  </td>
                </tr>
              ) : (
                users.map(u => (
                  <tr
                    key={u.id}
                    className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors cursor-pointer"
                    onClick={() => navigate(`/backoffice/users/${u.id}`)}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-[var(--color-primary)]/15 flex items-center justify-center text-xs font-bold text-[var(--color-primary)]">
                          {u.first_name[0]}{u.last_name[0]}
                        </div>
                        <div>
                          <div className="font-medium text-[var(--color-text)]">
                            {u.first_name} {u.last_name}
                          </div>
                          <div className="text-xs text-[var(--color-text-muted)]">{u.email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs capitalize text-[var(--color-text-muted)]">
                        {u.role?.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">
                      {u.department || '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span className={clsx(
                        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
                        STATUS_COLORS[u.status] || 'bg-gray-500/15 text-gray-400',
                      )}>
                        {STATUS_ICONS[u.status]}
                        {u.status?.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {u.mfa_enabled ? (
                        <Shield size={14} className="text-emerald-400" />
                      ) : (
                        <ShieldAlert size={14} className="text-[var(--color-text-muted)] opacity-40" />
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--color-text-muted)]">
                      {u.last_login_at
                        ? new Date(u.last_login_at).toLocaleDateString()
                        : 'Never'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="relative inline-block" onClick={e => e.stopPropagation()}>
                        <button
                          onClick={() => setActionMenuId(actionMenuId === u.id ? null : u.id)}
                          className="p-1 rounded hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]"
                        >
                          <MoreHorizontal size={16} />
                        </button>
                        {actionMenuId === u.id && (
                          <div className="absolute right-0 top-full mt-1 w-48 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-xl z-50 py-1">
                            <button
                              onClick={() => navigate(`/backoffice/users/${u.id}`)}
                              className="w-full text-left px-3 py-2 text-sm hover:bg-[var(--color-surface-hover)] flex items-center gap-2"
                            >
                              <Eye size={14} /> View Details
                            </button>
                            {u.status === 'active' && (
                              <button
                                onClick={() => handleAction(u.id, 'suspend')}
                                className="w-full text-left px-3 py-2 text-sm hover:bg-[var(--color-surface-hover)] flex items-center gap-2 text-amber-400"
                              >
                                <ShieldOff size={14} /> Suspend
                              </button>
                            )}
                            {u.status === 'suspended' && (
                              <button
                                onClick={() => handleAction(u.id, 'reactivate')}
                                className="w-full text-left px-3 py-2 text-sm hover:bg-[var(--color-surface-hover)] flex items-center gap-2 text-emerald-400"
                              >
                                <UserCheck size={14} /> Reactivate
                              </button>
                            )}
                            {u.status === 'locked' && (
                              <button
                                onClick={() => handleAction(u.id, 'unlock')}
                                className="w-full text-left px-3 py-2 text-sm hover:bg-[var(--color-surface-hover)] flex items-center gap-2 text-sky-400"
                              >
                                <Unlock size={14} /> Unlock
                              </button>
                            )}
                            {u.status !== 'deactivated' && (
                              <button
                                onClick={() => handleAction(u.id, 'deactivate')}
                                className="w-full text-left px-3 py-2 text-sm hover:bg-[var(--color-surface-hover)] flex items-center gap-2 text-red-400"
                              >
                                <UserX size={14} /> Deactivate
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
