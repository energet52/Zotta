import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft, Shield, ShieldOff, ShieldAlert, Lock, Unlock,
  UserCheck, UserX, Key, Monitor, Clock, RefreshCw,
  Save, Trash2, Eye, EyeOff, AlertTriangle,
} from 'lucide-react';
import { userApi } from '../../../api/endpoints';
import { clsx } from 'clsx';

interface UserDetailData {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  middle_name: string | null;
  display_name: string | null;
  phone: string | null;
  role: string;
  status: string;
  employee_id: string | null;
  department: string | null;
  job_title: string | null;
  timezone: string;
  language: string;
  profile_photo_url: string | null;
  mfa_enabled: boolean;
  last_login_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
  roles: Array<{
    id: number;
    role_id: number;
    role_name: string;
    granted_by: number | null;
    granted_at: string;
    expires_at: string | null;
    is_primary: boolean;
  }>;
  effective_permissions: string[];
  active_sessions_count: number;
  recent_login_attempts: Array<{
    id: number;
    ip_address: string | null;
    success: boolean;
    failure_reason: string | null;
    created_at: string;
  }>;
}

interface RoleBrief {
  id: number;
  name: string;
  description: string | null;
  is_system: boolean;
  is_active: boolean;
}

interface SessionRow {
  id: number;
  device_info: string | null;
  ip_address: string | null;
  is_active: boolean;
  created_at: string | null;
  last_activity_at: string | null;
}

type Tab = 'profile' | 'roles' | 'sessions' | 'security' | 'audit';

export default function UserDetail() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const [user, setUser] = useState<UserDetailData | null>(null);
  const [allRoles, setAllRoles] = useState<RoleBrief[]>([]);
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [tab, setTab] = useState<Tab>('profile');
  const [editForm, setEditForm] = useState<Record<string, string>>({});
  const [selectedRoleIds, setSelectedRoleIds] = useState<number[]>([]);
  const [resetPassword, setResetPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const load = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    try {
      const [userRes, rolesRes, sessRes] = await Promise.all([
        userApi.get(Number(userId)),
        userApi.listRoles(),
        userApi.getUserSessions(Number(userId)),
      ]);
      const u = userRes.data;
      setUser(u);
      setAllRoles(rolesRes.data);
      setSessions(sessRes.data);
      setEditForm({
        first_name: u.first_name,
        last_name: u.last_name,
        middle_name: u.middle_name || '',
        display_name: u.display_name || '',
        phone: u.phone || '',
        employee_id: u.employee_id || '',
        department: u.department || '',
        job_title: u.job_title || '',
        timezone: u.timezone || '',
        language: u.language || '',
      });
      setSelectedRoleIds(u.roles.map((r: { role_id: number }) => r.role_id));
    } catch (err) {
      console.error('Failed to load user', err);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => { load(); }, [load]);

  const handleSaveProfile = async () => {
    if (!userId) return;
    setSaving(true);
    try {
      const update: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(editForm)) {
        if (v !== (user as any)?.[k] && v !== '') {
          update[k] = v;
        } else if (v === '' && (user as any)?.[k]) {
          update[k] = null;
        }
      }
      if (Object.keys(update).length > 0) {
        await userApi.update(Number(userId), update);
      }
      await load();
    } catch (err) {
      console.error('Save failed', err);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveRoles = async () => {
    if (!userId) return;
    setSaving(true);
    try {
      await userApi.assignRoles(Number(userId), { role_ids: selectedRoleIds });
      await load();
    } catch (err) {
      console.error('Role save failed', err);
    } finally {
      setSaving(false);
    }
  };

  const handleAction = async (action: string) => {
    if (!userId) return;
    try {
      if (action === 'suspend') await userApi.suspend(Number(userId));
      else if (action === 'reactivate') await userApi.reactivate(Number(userId));
      else if (action === 'deactivate') await userApi.deactivate(Number(userId));
      else if (action === 'unlock') await userApi.unlock(Number(userId));
      else if (action === 'revoke-sessions') await userApi.revokeAllSessions(Number(userId));
      await load();
    } catch (err) {
      console.error('Action failed', err);
    }
  };

  const handleResetPassword = async () => {
    if (!userId || !resetPassword || resetPassword.length < 8) return;
    try {
      await userApi.resetPassword(Number(userId), { new_password: resetPassword });
      setResetPassword('');
      alert('Password reset successfully');
    } catch (err) {
      console.error('Password reset failed', err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-[var(--color-text-muted)]">
        <RefreshCw size={20} className="animate-spin mr-2" /> Loading user...
      </div>
    );
  }

  if (!user) {
    return (
      <div className="text-center py-20 text-[var(--color-text-muted)]">
        User not found.{' '}
        <Link to="/backoffice/users" className="text-[var(--color-primary)] underline">Go back</Link>
      </div>
    );
  }

  const statusColor: Record<string, string> = {
    active: 'text-emerald-400',
    suspended: 'text-amber-400',
    locked: 'text-red-400',
    deactivated: 'text-gray-400',
  };

  const tabs: { id: Tab; label: string }[] = [
    { id: 'profile', label: 'Profile' },
    { id: 'roles', label: 'Roles & Permissions' },
    { id: 'sessions', label: `Sessions (${user.active_sessions_count})` },
    { id: 'security', label: 'Security' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/backoffice/users')}
          className="p-2 rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
        >
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-bold text-[var(--color-text)]">
            {user.first_name} {user.last_name}
          </h1>
          <div className="flex items-center gap-3 text-sm text-[var(--color-text-muted)]">
            <span>{user.email}</span>
            <span className={clsx('capitalize font-medium', statusColor[user.status] || 'text-gray-400')}>
              {user.status?.replace(/_/g, ' ')}
            </span>
            {user.employee_id && <span>#{user.employee_id}</span>}
          </div>
        </div>

        {/* Quick actions */}
        <div className="flex items-center gap-2">
          {user.status === 'active' && (
            <button
              onClick={() => handleAction('suspend')}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-amber-500/30 text-amber-400 text-xs hover:bg-amber-500/10"
            >
              <ShieldOff size={14} /> Suspend
            </button>
          )}
          {user.status === 'suspended' && (
            <button
              onClick={() => handleAction('reactivate')}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-emerald-500/30 text-emerald-400 text-xs hover:bg-emerald-500/10"
            >
              <UserCheck size={14} /> Reactivate
            </button>
          )}
          {user.status === 'locked' && (
            <button
              onClick={() => handleAction('unlock')}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-sky-500/30 text-sky-400 text-xs hover:bg-sky-500/10"
            >
              <Unlock size={14} /> Unlock
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[var(--color-border)]">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={clsx(
              'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors',
              tab === t.id
                ? 'border-[var(--color-primary)] text-[var(--color-primary)]'
                : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'profile' && (
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              { key: 'first_name', label: 'First Name' },
              { key: 'last_name', label: 'Last Name' },
              { key: 'middle_name', label: 'Middle Name' },
              { key: 'display_name', label: 'Display Name' },
              { key: 'phone', label: 'Phone' },
              { key: 'employee_id', label: 'Employee ID' },
              { key: 'department', label: 'Department' },
              { key: 'job_title', label: 'Job Title' },
              { key: 'timezone', label: 'Timezone' },
              { key: 'language', label: 'Language' },
            ].map(({ key, label }) => (
              <div key={key}>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">{label}</label>
                <input
                  value={editForm[key] || ''}
                  onChange={e => setEditForm(prev => ({ ...prev, [key]: e.target.value }))}
                  className="w-full h-9 px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]/50"
                />
              </div>
            ))}
          </div>
          <div className="flex justify-end mt-6">
            <button
              onClick={handleSaveProfile}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
            >
              <Save size={14} />
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>
      )}

      {tab === 'roles' && (
        <div className="space-y-6">
          <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-6">
            <h3 className="text-sm font-semibold text-[var(--color-text)] mb-4">Assigned Roles</h3>
            <div className="space-y-2">
              {allRoles.filter(r => r.is_active).map(role => (
                <label
                  key={role.id}
                  className={clsx(
                    'flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors',
                    selectedRoleIds.includes(role.id)
                      ? 'border-[var(--color-primary)]/50 bg-[var(--color-primary)]/5'
                      : 'border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]',
                  )}
                >
                  <input
                    type="checkbox"
                    checked={selectedRoleIds.includes(role.id)}
                    onChange={() => {
                      setSelectedRoleIds(prev =>
                        prev.includes(role.id)
                          ? prev.filter(id => id !== role.id)
                          : [...prev, role.id]
                      );
                    }}
                    className="accent-[var(--color-primary)]"
                  />
                  <div className="flex-1">
                    <div className="text-sm font-medium text-[var(--color-text)]">
                      {role.name}
                      {role.is_system && (
                        <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-400">SYSTEM</span>
                      )}
                    </div>
                    {role.description && (
                      <div className="text-xs text-[var(--color-text-muted)]">{role.description}</div>
                    )}
                  </div>
                </label>
              ))}
            </div>
            <div className="flex justify-end mt-4">
              <button
                onClick={handleSaveRoles}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
              >
                <Save size={14} />
                {saving ? 'Saving...' : 'Save Roles'}
              </button>
            </div>
          </div>

          {/* Effective permissions */}
          <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-6">
            <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">
              Effective Permissions ({user.effective_permissions.length})
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {user.effective_permissions.map(p => (
                <span
                  key={p}
                  className="inline-block px-2 py-0.5 text-[10px] font-mono rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text-muted)]"
                >
                  {p}
                </span>
              ))}
              {user.effective_permissions.length === 0 && (
                <span className="text-xs text-[var(--color-text-muted)]">No permissions assigned</span>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === 'sessions' && (
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl overflow-hidden">
          <div className="px-6 py-4 flex items-center justify-between border-b border-[var(--color-border)]">
            <h3 className="text-sm font-semibold text-[var(--color-text)]">Active Sessions</h3>
            <button
              onClick={() => handleAction('revoke-sessions')}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-red-500/30 text-red-400 text-xs hover:bg-red-500/10"
            >
              <Trash2 size={12} /> Revoke All
            </button>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                <th className="text-left px-6 py-2 font-medium">Device</th>
                <th className="text-left px-6 py-2 font-medium">IP Address</th>
                <th className="text-left px-6 py-2 font-medium">Status</th>
                <th className="text-left px-6 py-2 font-medium">Started</th>
                <th className="text-left px-6 py-2 font-medium">Last Activity</th>
              </tr>
            </thead>
            <tbody>
              {sessions.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-8 text-[var(--color-text-muted)]">
                    No sessions
                  </td>
                </tr>
              ) : (
                sessions.map(s => (
                  <tr key={s.id} className="border-b border-[var(--color-border)]">
                    <td className="px-6 py-2">
                      <div className="flex items-center gap-2">
                        <Monitor size={14} className="text-[var(--color-text-muted)]" />
                        <span className="text-xs text-[var(--color-text)] truncate max-w-[200px]">
                          {s.device_info || 'Unknown device'}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-2 text-xs text-[var(--color-text-muted)]">{s.ip_address || '—'}</td>
                    <td className="px-6 py-2">
                      <span className={clsx(
                        'text-xs px-2 py-0.5 rounded-full',
                        s.is_active ? 'bg-emerald-500/15 text-emerald-400' : 'bg-gray-500/15 text-gray-400',
                      )}>
                        {s.is_active ? 'Active' : 'Expired'}
                      </span>
                    </td>
                    <td className="px-6 py-2 text-xs text-[var(--color-text-muted)]">
                      {s.created_at ? new Date(s.created_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-6 py-2 text-xs text-[var(--color-text-muted)]">
                      {s.last_activity_at ? new Date(s.last_activity_at).toLocaleString() : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'security' && (
        <div className="space-y-6">
          {/* MFA Status */}
          <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-6">
            <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">Multi-Factor Authentication</h3>
            <div className="flex items-center gap-3">
              {user.mfa_enabled ? (
                <>
                  <Shield size={20} className="text-emerald-400" />
                  <span className="text-sm text-emerald-400 font-medium">MFA Enabled</span>
                </>
              ) : (
                <>
                  <ShieldAlert size={20} className="text-amber-400" />
                  <span className="text-sm text-amber-400">MFA Not Configured</span>
                </>
              )}
            </div>
          </div>

          {/* Password Reset */}
          <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-6">
            <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">Reset Password</h3>
            <div className="flex items-center gap-3">
              <div className="relative flex-1 max-w-sm">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={resetPassword}
                  onChange={e => setResetPassword(e.target.value)}
                  placeholder="New password (min 8 chars)"
                  className="w-full h-9 px-3 pr-10 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]/50"
                />
                <button
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]"
                >
                  {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              <button
                onClick={handleResetPassword}
                disabled={!resetPassword || resetPassword.length < 8}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
              >
                <Key size={14} /> Reset
              </button>
            </div>
            <p className="text-xs text-[var(--color-text-muted)] mt-2">
              User will be required to change password on next login. All sessions will be revoked.
            </p>
          </div>

          {/* Recent Login Attempts */}
          <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-6">
            <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">Recent Login Attempts</h3>
            <div className="space-y-2">
              {user.recent_login_attempts.length === 0 ? (
                <p className="text-xs text-[var(--color-text-muted)]">No login attempts recorded</p>
              ) : (
                user.recent_login_attempts.map(a => (
                  <div
                    key={a.id}
                    className="flex items-center justify-between py-2 border-b border-[var(--color-border)] last:border-0"
                  >
                    <div className="flex items-center gap-2">
                      {a.success ? (
                        <UserCheck size={14} className="text-emerald-400" />
                      ) : (
                        <AlertTriangle size={14} className="text-red-400" />
                      )}
                      <span className={clsx(
                        'text-xs font-medium',
                        a.success ? 'text-emerald-400' : 'text-red-400',
                      )}>
                        {a.success ? 'Success' : `Failed: ${a.failure_reason || 'unknown'}`}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-[var(--color-text-muted)]">
                      <span>{a.ip_address || '—'}</span>
                      <span>{a.created_at ? new Date(a.created_at).toLocaleString() : '—'}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Danger zone */}
          {user.status !== 'deactivated' && (
            <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-6">
              <h3 className="text-sm font-semibold text-red-400 mb-2">Danger Zone</h3>
              <p className="text-xs text-[var(--color-text-muted)] mb-4">
                Deactivating a user permanently disables their access. This action revokes all sessions.
              </p>
              <button
                onClick={() => {
                  if (confirm(`Are you sure you want to deactivate ${user.email}?`)) {
                    handleAction('deactivate');
                  }
                }}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500 text-white text-sm font-medium hover:opacity-90"
              >
                <UserX size={14} /> Deactivate User
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


/* ── Create User Form ─────────────────────────────────────── */

export function CreateUserForm() {
  const navigate = useNavigate();
  const [allRoles, setAllRoles] = useState<RoleBrief[]>([]);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    phone: '',
    employee_id: '',
    department: '',
    job_title: '',
    role: 'applicant',
    role_ids: [] as number[],
    must_change_password: true,
  });

  useEffect(() => {
    userApi.listRoles().then(res => setAllRoles(res.data)).catch(() => {});
  }, []);

  const handleSubmit = async () => {
    if (!form.email || !form.password || !form.first_name || !form.last_name) return;
    setSaving(true);
    try {
      const res = await userApi.create(form);
      navigate(`/backoffice/users/${res.data.id}`);
    } catch (err) {
      console.error('Create user failed', err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/backoffice/users')}
          className="p-2 rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
        >
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-xl font-bold text-[var(--color-text)]">Create New User</h1>
      </div>

      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-6 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">First Name *</label>
            <input
              value={form.first_name}
              onChange={e => setForm(p => ({ ...p, first_name: e.target.value }))}
              className="w-full h-9 px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)]"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Last Name *</label>
            <input
              value={form.last_name}
              onChange={e => setForm(p => ({ ...p, last_name: e.target.value }))}
              className="w-full h-9 px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)]"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Email *</label>
          <input
            type="email"
            value={form.email}
            onChange={e => setForm(p => ({ ...p, email: e.target.value }))}
            className="w-full h-9 px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)]"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Password *</label>
          <input
            type="password"
            value={form.password}
            onChange={e => setForm(p => ({ ...p, password: e.target.value }))}
            className="w-full h-9 px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)]"
            placeholder="Min 8 characters"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Phone</label>
            <input
              value={form.phone}
              onChange={e => setForm(p => ({ ...p, phone: e.target.value }))}
              className="w-full h-9 px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)]"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Employee ID</label>
            <input
              value={form.employee_id}
              onChange={e => setForm(p => ({ ...p, employee_id: e.target.value }))}
              className="w-full h-9 px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)]"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Department</label>
            <input
              value={form.department}
              onChange={e => setForm(p => ({ ...p, department: e.target.value }))}
              className="w-full h-9 px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)]"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Job Title</label>
            <input
              value={form.job_title}
              onChange={e => setForm(p => ({ ...p, job_title: e.target.value }))}
              className="w-full h-9 px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)]"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Legacy Role</label>
          <select
            value={form.role}
            onChange={e => setForm(p => ({ ...p, role: e.target.value }))}
            className="w-full h-9 px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)]"
          >
            <option value="applicant">Applicant</option>
            <option value="junior_underwriter">Junior Underwriter</option>
            <option value="senior_underwriter">Senior Underwriter</option>
            <option value="admin">Admin</option>
          </select>
        </div>

        {/* Role assignment */}
        <div>
          <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-2">Assign Roles</label>
          <div className="space-y-1.5 max-h-48 overflow-y-auto">
            {allRoles.filter(r => r.is_active).map(role => (
              <label key={role.id} className="flex items-center gap-2 text-sm text-[var(--color-text)]">
                <input
                  type="checkbox"
                  checked={form.role_ids.includes(role.id)}
                  onChange={() => {
                    setForm(p => ({
                      ...p,
                      role_ids: p.role_ids.includes(role.id)
                        ? p.role_ids.filter(id => id !== role.id)
                        : [...p.role_ids, role.id],
                    }));
                  }}
                  className="accent-[var(--color-primary)]"
                />
                {role.name}
              </label>
            ))}
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm text-[var(--color-text)]">
          <input
            type="checkbox"
            checked={form.must_change_password}
            onChange={e => setForm(p => ({ ...p, must_change_password: e.target.checked }))}
            className="accent-[var(--color-primary)]"
          />
          Require password change on first login
        </label>

        <div className="flex justify-end pt-4">
          <button
            onClick={handleSubmit}
            disabled={saving || !form.email || !form.password || !form.first_name || !form.last_name}
            className="flex items-center gap-2 px-6 py-2 rounded-lg bg-[var(--color-primary)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
          >
            {saving ? <RefreshCw size={14} className="animate-spin" /> : <Save size={14} />}
            {saving ? 'Creating...' : 'Create User'}
          </button>
        </div>
      </div>
    </div>
  );
}

interface RoleBrief {
  id: number;
  name: string;
  description: string | null;
  is_system: boolean;
  is_active: boolean;
}
