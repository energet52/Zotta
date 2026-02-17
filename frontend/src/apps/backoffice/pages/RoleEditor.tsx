import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, Shield, Plus, Save, Search, ChevronDown, ChevronRight,
  Users, RefreshCw, Trash2, Edit3, Check, AlertTriangle, X,
} from 'lucide-react';
import { userApi } from '../../../api/endpoints';
import { clsx } from 'clsx';

interface RoleBrief {
  id: number;
  name: string;
  description: string | null;
  is_system: boolean;
  is_active: boolean;
}

interface PermissionRow {
  id: number;
  code: string;
  module: string;
  object: string;
  action: string;
  description: string | null;
}

interface RoleDetail {
  id: number;
  name: string;
  description: string | null;
  parent_role_id: number | null;
  is_system: boolean;
  is_active: boolean;
  permissions: PermissionRow[];
  user_count: number;
  created_at: string;
  updated_at: string;
}


/* ── Role List Page ─────────────────────────────────────────── */

export default function RoleEditor() {
  const navigate = useNavigate();
  const [roles, setRoles] = useState<RoleBrief[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await userApi.listRoles();
      setRoles(res.data);
    } catch (err) {
      console.error('Failed to load roles', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/backoffice/users')}
            className="p-2 rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
          >
            <ArrowLeft size={18} />
          </button>
          <div>
            <h1 className="text-xl font-bold text-[var(--color-text)]">Roles & Permissions</h1>
            <p className="text-sm text-[var(--color-text-muted)]">
              Manage roles and their permission assignments
            </p>
          </div>
        </div>
        <button
          onClick={() => navigate('/backoffice/users/roles/new')}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white text-sm font-medium hover:opacity-90"
        >
          <Plus size={16} /> Create Role
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {loading ? (
          <div className="col-span-full text-center py-12 text-[var(--color-text-muted)]">
            <RefreshCw size={20} className="animate-spin mx-auto mb-2" />
            Loading roles...
          </div>
        ) : (
          roles.filter(role => role.name !== 'Applicant').map(role => (
            <div
              key={role.id}
              onClick={() => navigate(`/backoffice/users/roles/${role.id}`)}
              className={clsx(
                'bg-[var(--color-surface)] border rounded-xl p-5 cursor-pointer transition-all hover:border-[var(--color-primary)]/50 hover:shadow-lg',
                role.is_active ? 'border-[var(--color-border)]' : 'border-[var(--color-border)] opacity-60',
              )}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Shield size={16} className="text-[var(--color-primary)]" />
                  <h3 className="font-semibold text-[var(--color-text)]">{role.name}</h3>
                </div>
                {role.is_system && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-400">SYSTEM</span>
                )}
              </div>
              <p className="text-xs text-[var(--color-text-muted)] mb-3 line-clamp-2">
                {role.description || 'No description'}
              </p>
              <div className="flex items-center justify-between text-xs text-[var(--color-text-muted)]">
                <span className={clsx(
                  'px-2 py-0.5 rounded-full',
                  role.is_active ? 'bg-emerald-500/15 text-emerald-400' : 'bg-gray-500/15 text-gray-400',
                )}>
                  {role.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}


/* ── Role Detail / Edit Page ──────────────────────────────── */

export function RoleDetailPage() {
  const { roleId } = useParams<{ roleId: string }>();
  const navigate = useNavigate();
  const isNew = roleId === 'new';

  const [role, setRole] = useState<RoleDetail | null>(null);
  const [allPermissions, setAllPermissions] = useState<PermissionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [selectedPerms, setSelectedPerms] = useState<Set<string>>(new Set());
  const [searchPerm, setSearchPerm] = useState('');
  const [expandedModules, setExpandedModules] = useState<Set<string>>(new Set());

  // Delete dialog state
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [allRoles, setAllRoles] = useState<RoleBrief[]>([]);
  const [reassignRoleId, setReassignRoleId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const permsRes = await userApi.listPermissions();
      setAllPermissions(permsRes.data);

      if (!isNew && roleId) {
        const roleRes = await userApi.getRole(Number(roleId));
        const r = roleRes.data;
        setRole(r);
        setName(r.name);
        setDescription(r.description || '');
        setSelectedPerms(new Set(r.permissions.map((p: PermissionRow) => p.code)));
      }
    } catch (err) {
      console.error('Failed to load role', err);
    } finally {
      setLoading(false);
    }
  }, [roleId, isNew]);

  useEffect(() => { load(); }, [load]);

  // Group permissions by module
  const permsByModule = useMemo(() => {
    const map = new Map<string, PermissionRow[]>();
    for (const p of allPermissions) {
      const list = map.get(p.module) || [];
      list.push(p);
      map.set(p.module, list);
    }
    return map;
  }, [allPermissions]);

  const filteredModules = useMemo(() => {
    const q = searchPerm.toLowerCase();
    if (!q) return Array.from(permsByModule.entries());
    return Array.from(permsByModule.entries()).filter(([mod, perms]) =>
      mod.includes(q) || perms.some(p => p.code.includes(q) || p.description?.toLowerCase().includes(q))
    );
  }, [permsByModule, searchPerm]);

  const toggleModule = (mod: string) => {
    setExpandedModules(prev => {
      const next = new Set(prev);
      if (next.has(mod)) next.delete(mod);
      else next.add(mod);
      return next;
    });
  };

  const togglePerm = (code: string) => {
    setSelectedPerms(prev => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  const toggleModuleAll = (mod: string, perms: PermissionRow[]) => {
    const allSelected = perms.every(p => selectedPerms.has(p.code));
    setSelectedPerms(prev => {
      const next = new Set(prev);
      for (const p of perms) {
        if (allSelected) next.delete(p.code);
        else next.add(p.code);
      }
      return next;
    });
  };

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const codes = Array.from(selectedPerms);
      if (isNew) {
        const res = await userApi.createRole({ name, description, permission_codes: codes });
        navigate(`/backoffice/users/roles/${res.data.id}`, { replace: true });
      } else if (roleId) {
        await userApi.updateRole(Number(roleId), {
          name, description, permission_codes: codes,
        });
        await load();
      }
    } catch (err) {
      console.error('Save failed', err);
    } finally {
      setSaving(false);
    }
  };

  const openDeleteDialog = async () => {
    setDeleteError('');
    setReassignRoleId(null);
    try {
      const res = await userApi.listRoles();
      setAllRoles(res.data.filter((r: RoleBrief) => r.id !== Number(roleId)));
    } catch { /* ignore */ }
    setShowDeleteDialog(true);
  };

  const handleDelete = async () => {
    if (!reassignRoleId || !roleId) return;
    setDeleting(true);
    setDeleteError('');
    try {
      await userApi.deleteRole(Number(roleId), reassignRoleId);
      navigate('/backoffice/users/roles', { replace: true });
    } catch (err: any) {
      setDeleteError(err?.response?.data?.detail || 'Failed to delete role');
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-[var(--color-text-muted)]">
        <RefreshCw size={20} className="animate-spin mr-2" /> Loading...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/backoffice/users/roles')}
          className="p-2 rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
        >
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-bold text-[var(--color-text)]">
            {isNew ? 'Create Role' : `Edit: ${role?.name || ''}`}
          </h1>
        </div>
        <div className="flex items-center gap-2">
          {!isNew && role && !role.is_system && (
            <button
              onClick={openDeleteDialog}
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-red-500/30 text-red-400 text-sm font-medium hover:bg-red-500/10 transition-colors"
            >
              <Trash2 size={14} /> Delete
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={saving || !name.trim()}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
          >
            {saving ? <RefreshCw size={14} className="animate-spin" /> : <Save size={14} />}
            {saving ? 'Saving...' : 'Save Role'}
          </button>
        </div>
      </div>

      {/* Name & description */}
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-6 space-y-4">
        <div>
          <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Role Name *</label>
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            disabled={role?.is_system}
            className="w-full h-9 px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)] disabled:opacity-50"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Description</label>
          <textarea
            value={description}
            onChange={e => setDescription(e.target.value)}
            rows={2}
            className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)] resize-none"
          />
        </div>
        {role && !isNew && (
          <div className="flex items-center gap-4 text-xs text-[var(--color-text-muted)]">
            <span>Users assigned: <strong className="text-[var(--color-text)]">{role.user_count}</strong></span>
            {role.is_system && <span className="px-2 py-0.5 rounded bg-sky-500/15 text-sky-400">System Role</span>}
          </div>
        )}
      </div>

      {/* Permissions */}
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-[var(--color-text)]">
            Permissions ({selectedPerms.size} / {allPermissions.length})
          </h3>
          <div className="relative w-64">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
            <input
              value={searchPerm}
              onChange={e => setSearchPerm(e.target.value)}
              placeholder="Filter permissions..."
              className="w-full h-8 pl-8 pr-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-xs text-[var(--color-text)] focus:outline-none"
            />
          </div>
        </div>

        <div className="space-y-1">
          {filteredModules.map(([mod, perms]) => {
            const isExpanded = expandedModules.has(mod) || searchPerm.trim().length > 0;
            const selectedCount = perms.filter(p => selectedPerms.has(p.code)).length;
            const allSelected = selectedCount === perms.length;

            return (
              <div key={mod} className="border border-[var(--color-border)] rounded-lg overflow-hidden">
                <button
                  onClick={() => toggleModule(mod)}
                  className="w-full flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
                >
                  {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  <span className="capitalize">{mod}</span>
                  <span className="text-xs text-[var(--color-text-muted)] ml-auto">
                    {selectedCount}/{perms.length}
                  </span>
                  <button
                    onClick={e => { e.stopPropagation(); toggleModuleAll(mod, perms); }}
                    className={clsx(
                      'ml-2 text-[10px] px-1.5 py-0.5 rounded',
                      allSelected ? 'bg-[var(--color-primary)]/15 text-[var(--color-primary)]' : 'bg-[var(--color-bg)] text-[var(--color-text-muted)]',
                    )}
                  >
                    {allSelected ? 'Deselect all' : 'Select all'}
                  </button>
                </button>

                {isExpanded && (
                  <div className="px-4 pb-3 space-y-1">
                    {perms.map(p => (
                      <label
                        key={p.code}
                        className="flex items-center gap-3 py-1.5 cursor-pointer hover:bg-[var(--color-surface-hover)] rounded px-2 -mx-2"
                      >
                        <input
                          type="checkbox"
                          checked={selectedPerms.has(p.code)}
                          onChange={() => togglePerm(p.code)}
                          className="accent-[var(--color-primary)]"
                        />
                        <div className="flex-1">
                          <span className="text-xs font-mono text-[var(--color-text)]">{p.code}</span>
                          {p.description && (
                            <span className="ml-2 text-[10px] text-[var(--color-text-muted)]">{p.description}</span>
                          )}
                        </div>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Delete Confirmation Dialog ── */}
      {showDeleteDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-2xl shadow-2xl w-full max-w-md mx-4">
            <div className="flex items-center justify-between p-5 border-b border-[var(--color-border)]">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-red-500/15">
                  <AlertTriangle size={18} className="text-red-400" />
                </div>
                <h3 className="text-lg font-semibold text-[var(--color-text)]">Delete Role</h3>
              </div>
              <button
                onClick={() => setShowDeleteDialog(false)}
                className="p-1.5 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
              >
                <X size={16} />
              </button>
            </div>

            <div className="p-5 space-y-4">
              <p className="text-sm text-[var(--color-text-muted)]">
                You are about to permanently delete the role <strong className="text-[var(--color-text)]">{role?.name}</strong>.
                {(role?.user_count ?? 0) > 0 && (
                  <> This role has <strong className="text-[var(--color-text)]">{role?.user_count} user(s)</strong> assigned.
                  They will be reassigned to the role you select below.</>
                )}
              </p>

              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1.5">
                  Reassign users to *
                </label>
                <select
                  value={reassignRoleId ?? ''}
                  onChange={e => setReassignRoleId(Number(e.target.value) || null)}
                  className="w-full h-10 px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
                >
                  <option value="">Select a role...</option>
                  {allRoles.filter(r => r.is_active).map(r => (
                    <option key={r.id} value={r.id}>{r.name}</option>
                  ))}
                </select>
              </div>

              {deleteError && (
                <p className="text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-2">{deleteError}</p>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 p-5 border-t border-[var(--color-border)]">
              <button
                onClick={() => setShowDeleteDialog(false)}
                className="px-4 py-2 rounded-lg border border-[var(--color-border)] text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={!reassignRoleId || deleting}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500 text-white text-sm font-medium hover:bg-red-600 disabled:opacity-50 transition-colors"
              >
                {deleting ? <RefreshCw size={14} className="animate-spin" /> : <Trash2 size={14} />}
                {deleting ? 'Deleting...' : 'Delete Role'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
