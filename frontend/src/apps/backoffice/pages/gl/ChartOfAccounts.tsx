import { useEffect, useState, useMemo, useCallback } from 'react';
import {
  ChevronRight,
  ChevronDown,
  Search,
  Plus,
  X,
  FolderTree,
  Edit2,
  Snowflake,
  Loader2,
  AlertCircle,
  FolderOpen,
} from 'lucide-react';
import Card from '../../../../components/ui/Card';
import Button from '../../../../components/ui/Button';
import Input from '../../../../components/ui/Input';
import { glApi, type GLAccount } from '../../../../api/glApi';

/* ── helpers ─────────────────────────────────── */

const fmt = (n: number) =>
  n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const CATEGORIES = ['Asset', 'Liability', 'Equity', 'Revenue', 'Expense'] as const;
const CATEGORY_COLORS: Record<string, string> = {
  Asset: 'bg-blue-500/20 text-blue-400',
  Liability: 'bg-amber-500/20 text-amber-400',
  Equity: 'bg-purple-500/20 text-purple-400',
  Revenue: 'bg-emerald-500/20 text-emerald-400',
  Expense: 'bg-red-500/20 text-red-400',
};
const STATUS_COLORS: Record<string, string> = {
  active: 'bg-emerald-500/20 text-emerald-400',
  frozen: 'bg-sky-500/20 text-sky-400',
  closed: 'bg-red-500/20 text-red-400',
};

interface TreeNode extends GLAccount {
  children: TreeNode[];
}

function buildTree(accounts: GLAccount[]): TreeNode[] {
  const map = new Map<number, TreeNode>();
  const roots: TreeNode[] = [];

  accounts.forEach((a) => map.set(a.id, { ...a, children: [] }));
  accounts.forEach((a) => {
    const node = map.get(a.id)!;
    if (a.parent_id && map.has(a.parent_id)) {
      map.get(a.parent_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  });

  const sort = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => a.account_code.localeCompare(b.account_code));
    nodes.forEach((n) => sort(n.children));
  };
  sort(roots);
  return roots;
}

/* ── account row ─────────────────────────────── */

function AccountRow({
  node,
  depth,
  expanded,
  toggleExpand,
  onEdit,
  balances,
}: {
  node: TreeNode;
  depth: number;
  expanded: Set<number>;
  toggleExpand: (id: number) => void;
  onEdit: (a: GLAccount) => void;
  balances: Map<number, number>;
}) {
  const hasChildren = node.children.length > 0;
  const isOpen = expanded.has(node.id);

  return (
    <>
      <tr className="group border-b border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors">
        {/* Tree + Name */}
        <td className="py-3 pr-3 whitespace-nowrap">
          <div className="flex items-center" style={{ paddingLeft: `${depth * 24 + 12}px` }}>
            {/* Connector lines */}
            {depth > 0 && (
              <span
                className="absolute left-0 top-0 bottom-0 border-l border-dashed border-[var(--color-border)]"
                style={{ marginLeft: `${(depth - 1) * 24 + 22}px` }}
              />
            )}

            {/* Expand / Collapse */}
            {hasChildren ? (
              <button
                onClick={() => toggleExpand(node.id)}
                className="mr-2 p-0.5 rounded hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]"
              >
                {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              </button>
            ) : (
              <span className="mr-2 w-5" />
            )}

            <span className="font-mono text-xs text-[var(--color-text-muted)] mr-3 min-w-0 sm:min-w-[72px]">
              {node.account_code}
            </span>
            <span className="font-medium text-[var(--color-text)]">{node.name}</span>
            {node.is_control_account && (
              <span className="ml-2 text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-[var(--color-primary)]/15 text-[var(--color-primary)]">
                Control
              </span>
            )}
            {node.is_system_account && (
              <span className="ml-2 text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-[var(--color-text-muted)]/15 text-[var(--color-text-muted)]">
                System
              </span>
            )}
          </div>
        </td>

        {/* Category */}
        <td className="py-3 px-3">
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${CATEGORY_COLORS[node.account_category] ?? 'bg-gray-500/20 text-gray-400'}`}>
            {node.account_category}
          </span>
        </td>

        {/* Type */}
        <td className="py-3 px-3 text-sm text-[var(--color-text-muted)] capitalize">
          {node.account_type.replace(/_/g, ' ')}
        </td>

        {/* Status */}
        <td className="py-3 px-3">
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${STATUS_COLORS[node.status] ?? 'bg-gray-500/20 text-gray-400'}`}>
            {node.status}
          </span>
        </td>

        {/* Balance */}
        <td className="py-3 px-3 text-right font-mono text-sm">
          {balances.has(node.id) ? fmt(balances.get(node.id)!) : '—'}
        </td>

        {/* Actions */}
        <td className="py-3 pl-3 text-right">
          <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={() => onEdit(node)}
              className="p-1.5 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              title="Edit account"
            >
              <Edit2 size={14} />
            </button>
          </div>
        </td>
      </tr>

      {/* Children */}
      {isOpen &&
        node.children.map((child) => (
          <AccountRow
            key={child.id}
            node={child}
            depth={depth + 1}
            expanded={expanded}
            toggleExpand={toggleExpand}
            onEdit={onEdit}
            balances={balances}
          />
        ))}
    </>
  );
}

/* ── create / edit modal ─────────────────────── */

interface ModalProps {
  account: GLAccount | null;
  accounts: GLAccount[];
  onClose: () => void;
  onSave: (data: Record<string, unknown>) => Promise<void>;
  saving: boolean;
}

function AccountModal({ account, accounts, onClose, onSave, saving }: ModalProps) {
  const [name, setName] = useState(account?.name ?? '');
  const [category, setCategory] = useState(account?.account_category ?? 'Asset');
  const [type, setType] = useState(account?.account_type ?? 'detail');
  const [parentId, setParentId] = useState<string>(account?.parent_id?.toString() ?? '');
  const [code, setCode] = useState(account?.account_code ?? '');
  const [description, setDescription] = useState(account?.description ?? '');
  const [isControl, setIsControl] = useState(account?.is_control_account ?? false);

  const parentOptions = useMemo(
    () => accounts.filter((a) => a.id !== account?.id).sort((a, b) => a.account_code.localeCompare(b.account_code)),
    [accounts, account],
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload: Record<string, unknown> = { name, description, is_control_account: isControl };
    if (!account) {
      payload.account_category = category;
      payload.account_type = type;
      if (parentId) payload.parent_id = Number(parentId);
      if (code) payload.account_code = code;
    }
    await onSave(payload);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <Card className="w-full max-w-lg mx-4 shadow-2xl" padding="lg">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-[var(--color-text)]">
            {account ? 'Edit Account' : 'Create Account'}
          </h2>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input label="Account Name" value={name} onChange={(e) => setName(e.target.value)} required />
            <Input label="Account Code" value={code} onChange={(e) => setCode(e.target.value)} disabled={!!account} placeholder="Auto-generated" />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="w-full">
              <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                disabled={!!account}
                className="w-full px-3 py-2 border rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] disabled:opacity-50"
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            <div className="w-full">
              <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">Account Type</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value)}
                disabled={!!account}
                className="w-full px-3 py-2 border rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] disabled:opacity-50"
              >
                <option value="detail">Detail</option>
                <option value="header">Header</option>
                <option value="total">Total</option>
              </select>
            </div>
          </div>

          <div className="w-full">
            <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">Parent Account</label>
            <select
              value={parentId}
              onChange={(e) => setParentId(e.target.value)}
              disabled={!!account}
              className="w-full px-3 py-2 border rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] disabled:opacity-50"
            >
              <option value="">— None (Top-level) —</option>
              {parentOptions.map((a) => (
                <option key={a.id} value={a.id}>{a.account_code} — {a.name}</option>
              ))}
            </select>
          </div>

          <div className="w-full">
            <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] resize-none"
            />
          </div>

          <label className="flex items-center gap-2 text-sm text-[var(--color-text)]">
            <input
              type="checkbox"
              checked={isControl}
              onChange={(e) => setIsControl(e.target.checked)}
              className="rounded border-[var(--color-border)] text-[var(--color-primary)] focus:ring-[var(--color-primary)]"
            />
            Control Account
          </label>

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" type="button" onClick={onClose}>Cancel</Button>
            <Button type="submit" isLoading={saving}>
              {account ? 'Update Account' : 'Create Account'}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

/* ── main page ───────────────────────────────── */

export default function ChartOfAccounts() {
  const [accounts, setAccounts] = useState<GLAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [modalOpen, setModalOpen] = useState(false);
  const [editAccount, setEditAccount] = useState<GLAccount | null>(null);
  const [saving, setSaving] = useState(false);
  const [balances] = useState<Map<number, number>>(new Map());

  const fetchAccounts = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const params: Record<string, string> = {};
      if (categoryFilter) params.category = categoryFilter;
      if (statusFilter) params.status = statusFilter;
      if (search) params.search = search;
      const { data } = await glApi.getAccounts(params);
      setAccounts(data);
    } catch {
      setError('Failed to load accounts');
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, statusFilter, search]);

  useEffect(() => {
    fetchAccounts();
  }, [fetchAccounts]);

  const tree = useMemo(() => buildTree(accounts), [accounts]);

  const toggleExpand = (id: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const expandAll = () => {
    setExpanded(new Set(accounts.map((a) => a.id)));
  };

  const collapseAll = () => {
    setExpanded(new Set());
  };

  const openCreate = () => {
    setEditAccount(null);
    setModalOpen(true);
  };

  const openEdit = (a: GLAccount) => {
    setEditAccount(a);
    setModalOpen(true);
  };

  const handleSave = async (data: Record<string, unknown>) => {
    setSaving(true);
    try {
      if (editAccount) {
        await glApi.updateAccount(editAccount.id, data as { name?: string; description?: string; is_control_account?: boolean });
      } else {
        await glApi.createAccount(data as Parameters<typeof glApi.createAccount>[0]);
      }
      setModalOpen(false);
      setEditAccount(null);
      await fetchAccounts();
    } catch {
      // handled by modal
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-[var(--color-primary)]/10">
            <FolderTree size={22} className="text-[var(--color-primary)]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-text)]">Chart of Accounts</h1>
            <p className="text-sm text-[var(--color-text-muted)]">
              {accounts.length} account{accounts.length !== 1 ? 's' : ''} configured
            </p>
          </div>
        </div>
        <Button onClick={openCreate}>
          <Plus size={16} className="mr-2" />
          New Account
        </Button>
      </div>

      {/* Filters */}
      <Card padding="sm">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-0 sm:min-w-[220px]">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
            <input
              type="text"
              placeholder="Search accounts…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            />
          </div>

          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          >
            <option value="">All Categories</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          >
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="frozen">Frozen</option>
            <option value="closed">Closed</option>
          </select>

          <div className="flex items-center gap-1 ml-auto">
            <Button variant="ghost" size="sm" onClick={expandAll}>
              <FolderOpen size={14} className="mr-1" /> Expand
            </Button>
            <Button variant="ghost" size="sm" onClick={collapseAll}>
              <Snowflake size={14} className="mr-1" /> Collapse
            </Button>
          </div>
        </div>
      </Card>

      {/* Table */}
      <Card padding="none">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-[var(--color-text-muted)]">
            <Loader2 size={24} className="animate-spin mr-3" />
            Loading accounts…
          </div>
        ) : error ? (
          <div className="flex items-center justify-center py-20 text-[var(--color-danger)]">
            <AlertCircle size={20} className="mr-2" />
            {error}
          </div>
        ) : accounts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-[var(--color-text-muted)]">
            <FolderTree size={40} className="mb-3 opacity-40" />
            <p className="text-lg font-medium">No accounts found</p>
            <p className="text-sm mt-1">Create your first GL account to get started.</p>
          </div>
        ) : (
          <div className="overflow-x-auto max-w-full">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] text-xs uppercase tracking-wider">
                  <th className="py-3 px-4 text-left font-medium">Account</th>
                  <th className="py-3 px-3 text-left font-medium">Category</th>
                  <th className="py-3 px-3 text-left font-medium">Type</th>
                  <th className="py-3 px-3 text-left font-medium">Status</th>
                  <th className="py-3 px-3 text-right font-medium">Balance</th>
                  <th className="py-3 px-3 w-16" />
                </tr>
              </thead>
              <tbody>
                {tree.map((node) => (
                  <AccountRow
                    key={node.id}
                    node={node}
                    depth={0}
                    expanded={expanded}
                    toggleExpand={toggleExpand}
                    onEdit={openEdit}
                    balances={balances}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Modal */}
      {modalOpen && (
        <AccountModal
          account={editAccount}
          accounts={accounts}
          onClose={() => { setModalOpen(false); setEditAccount(null); }}
          onSave={handleSave}
          saving={saving}
        />
      )}
    </div>
  );
}
