import { useEffect, useState, useCallback } from 'react';
import {
  BookOpen,
  Plus,
  ChevronDown,
  ChevronRight,
  Search,
  X,
  Loader2,
  AlertCircle,
  Trash2,
  ArrowRight,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Send,
  FileText,
} from 'lucide-react';
import Card from '../../../../components/ui/Card';
import Button from '../../../../components/ui/Button';
import Input from '../../../../components/ui/Input';
import {
  glApi,
  type JournalEntry,
  type JournalLineInput,
  type GLAccount,
  type PaginatedEntries,
} from '../../../../api/glApi';

/* ── helpers ─────────────────────────────────── */

const fmt = (n: number) =>
  n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });

const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-gray-500/20 text-gray-400',
  pending: 'bg-amber-500/20 text-amber-400',
  approved: 'bg-sky-500/20 text-sky-400',
  posted: 'bg-emerald-500/20 text-emerald-400',
  rejected: 'bg-red-500/20 text-red-400',
  reversed: 'bg-purple-500/20 text-purple-400',
};

const STATUS_TABS = ['All', 'Draft', 'Pending', 'Approved', 'Posted', 'Rejected', 'Reversed'] as const;

/* ── new entry modal ─────────────────────────── */

interface LineForm {
  key: number;
  gl_account_id: string;
  debit_amount: string;
  credit_amount: string;
  description: string;
}

function NewEntryModal({
  accounts,
  onClose,
  onCreated,
}: {
  accounts: GLAccount[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [description, setDescription] = useState('');
  const [sourceType, setSourceType] = useState('manual');
  const [transactionDate, setTransactionDate] = useState(new Date().toISOString().slice(0, 10));
  const [narrative, setNarrative] = useState('');
  const [lines, setLines] = useState<LineForm[]>([
    { key: 1, gl_account_id: '', debit_amount: '', credit_amount: '', description: '' },
    { key: 2, gl_account_id: '', debit_amount: '', credit_amount: '', description: '' },
  ]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  let nextKey = lines.reduce((m, l) => Math.max(m, l.key), 0) + 1;

  const addLine = () => {
    setLines([...lines, { key: nextKey++, gl_account_id: '', debit_amount: '', credit_amount: '', description: '' }]);
  };

  const removeLine = (key: number) => {
    if (lines.length <= 2) return;
    setLines(lines.filter((l) => l.key !== key));
  };

  const updateLine = (key: number, field: keyof LineForm, value: string) => {
    setLines(lines.map((l) => (l.key === key ? { ...l, [field]: value } : l)));
  };

  const totalDebits = lines.reduce((s, l) => s + (parseFloat(l.debit_amount) || 0), 0);
  const totalCredits = lines.reduce((s, l) => s + (parseFloat(l.credit_amount) || 0), 0);
  const isBalanced = Math.abs(totalDebits - totalCredits) < 0.005 && totalDebits > 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isBalanced) return;
    setError('');
    setSaving(true);
    try {
      const mappedLines: JournalLineInput[] = lines
        .filter((l) => l.gl_account_id)
        .map((l) => ({
          gl_account_id: Number(l.gl_account_id),
          debit_amount: parseFloat(l.debit_amount) || 0,
          credit_amount: parseFloat(l.credit_amount) || 0,
          description: l.description || undefined,
        }));
      await glApi.createEntry({
        description,
        source_type: sourceType,
        transaction_date: transactionDate,
        narrative: narrative || undefined,
        lines: mappedLines,
      });
      onCreated();
    } catch {
      setError('Failed to create journal entry');
    } finally {
      setSaving(false);
    }
  };

  const sortedAccounts = [...accounts]
    .filter((a) => a.status === 'active')
    .sort((a, b) => a.account_code.localeCompare(b.account_code));

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 backdrop-blur-sm overflow-y-auto py-8">
      <Card className="w-full max-w-3xl mx-4 shadow-2xl" padding="lg">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-[var(--color-text)]">New Journal Entry</h2>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-3 gap-4">
            <Input label="Description" value={description} onChange={(e) => setDescription(e.target.value)} required />
            <Input label="Transaction Date" type="date" value={transactionDate} onChange={(e) => setTransactionDate(e.target.value)} />
            <div className="w-full">
              <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">Source</label>
              <select
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              >
                <option value="manual">Manual</option>
                <option value="loan_disbursement">Loan Disbursement</option>
                <option value="loan_repayment">Loan Repayment</option>
                <option value="fee">Fee</option>
                <option value="adjustment">Adjustment</option>
              </select>
            </div>
          </div>

          <div className="w-full">
            <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">Narrative</label>
            <textarea
              value={narrative}
              onChange={(e) => setNarrative(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] resize-none"
              placeholder="Optional narrative…"
            />
          </div>

          {/* Lines */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-[var(--color-text)]">Journal Lines</h3>
              <Button type="button" variant="ghost" size="sm" onClick={addLine}>
                <Plus size={14} className="mr-1" /> Add Line
              </Button>
            </div>

            <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] text-xs uppercase tracking-wider bg-[var(--color-surface-hover)]/50">
                    <th className="py-2 px-3 text-left font-medium">Account</th>
                    <th className="py-2 px-3 text-right font-medium w-32">Debit</th>
                    <th className="py-2 px-3 text-right font-medium w-32">Credit</th>
                    <th className="py-2 px-3 text-left font-medium">Memo</th>
                    <th className="py-2 px-3 w-10" />
                  </tr>
                </thead>
                <tbody>
                  {lines.map((line) => (
                    <tr key={line.key} className="border-b border-[var(--color-border)] last:border-b-0">
                      <td className="py-2 px-3">
                        <select
                          value={line.gl_account_id}
                          onChange={(e) => updateLine(line.key, 'gl_account_id', e.target.value)}
                          className="w-full px-2 py-1.5 text-sm rounded border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                          required
                        >
                          <option value="">Select account…</option>
                          {sortedAccounts.map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.account_code} — {a.name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="py-2 px-3">
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          value={line.debit_amount}
                          onChange={(e) => updateLine(line.key, 'debit_amount', e.target.value)}
                          placeholder="0.00"
                          className="w-full px-2 py-1.5 text-sm text-right font-mono rounded border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                        />
                      </td>
                      <td className="py-2 px-3">
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          value={line.credit_amount}
                          onChange={(e) => updateLine(line.key, 'credit_amount', e.target.value)}
                          placeholder="0.00"
                          className="w-full px-2 py-1.5 text-sm text-right font-mono rounded border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                        />
                      </td>
                      <td className="py-2 px-3">
                        <input
                          type="text"
                          value={line.description}
                          onChange={(e) => updateLine(line.key, 'description', e.target.value)}
                          placeholder="Line memo…"
                          className="w-full px-2 py-1.5 text-sm rounded border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                        />
                      </td>
                      <td className="py-2 px-3">
                        <button
                          type="button"
                          onClick={() => removeLine(line.key)}
                          disabled={lines.length <= 2}
                          className="p-1 rounded hover:bg-red-500/10 text-[var(--color-text-muted)] hover:text-red-400 disabled:opacity-30"
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-[var(--color-border)] bg-[var(--color-surface-hover)]/50 font-medium">
                    <td className="py-2 px-3 text-right text-xs uppercase text-[var(--color-text-muted)]">Totals</td>
                    <td className="py-2 px-3 text-right font-mono text-sm">{fmt(totalDebits)}</td>
                    <td className="py-2 px-3 text-right font-mono text-sm">{fmt(totalCredits)}</td>
                    <td colSpan={2} className="py-2 px-3">
                      {totalDebits > 0 || totalCredits > 0 ? (
                        isBalanced ? (
                          <span className="flex items-center gap-1 text-xs text-emerald-400">
                            <CheckCircle2 size={14} /> Balanced
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-xs text-[var(--color-danger)]">
                            <AlertCircle size={14} /> Difference: {fmt(Math.abs(totalDebits - totalCredits))}
                          </span>
                        )
                      ) : null}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          {error && (
            <p className="text-sm text-[var(--color-danger)] flex items-center gap-1">
              <AlertCircle size={14} /> {error}
            </p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" type="button" onClick={onClose}>Cancel</Button>
            <Button type="submit" isLoading={saving} disabled={!isBalanced}>
              <Plus size={16} className="mr-2" /> Create Entry
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

/* ── expanded row detail ─────────────────────── */

function EntryDetail({
  entry,
  onAction,
  acting,
}: {
  entry: JournalEntry;
  onAction: (action: string, id: number) => void;
  acting: boolean;
}) {
  const [reason, setReason] = useState('');

  const actions: { label: string; action: string; variant: 'primary' | 'success' | 'danger' | 'warning' | 'secondary'; icon: React.ReactNode; show: boolean }[] = [
    { label: 'Submit', action: 'submit', variant: 'primary', icon: <Send size={14} />, show: entry.status === 'draft' },
    { label: 'Approve', action: 'approve', variant: 'success', icon: <CheckCircle2 size={14} />, show: entry.status === 'pending' },
    { label: 'Post', action: 'post', variant: 'success', icon: <ArrowRight size={14} />, show: entry.status === 'approved' },
    { label: 'Reject', action: 'reject', variant: 'danger', icon: <XCircle size={14} />, show: entry.status === 'pending' },
    { label: 'Reverse', action: 'reverse', variant: 'warning', icon: <RotateCcw size={14} />, show: entry.status === 'posted' },
  ];

  return (
    <tr>
      <td colSpan={7} className="p-0">
        <div className="bg-[var(--color-surface-hover)]/40 border-t border-[var(--color-border)] px-6 py-4 space-y-4">
          {/* Lines table */}
          <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wider text-[var(--color-text-muted)] bg-[var(--color-surface)]">
                  <th className="py-2 px-3 text-left font-medium">#</th>
                  <th className="py-2 px-3 text-left font-medium">Account</th>
                  <th className="py-2 px-3 text-left font-medium">Description</th>
                  <th className="py-2 px-3 text-right font-medium">Debit</th>
                  <th className="py-2 px-3 text-right font-medium">Credit</th>
                </tr>
              </thead>
              <tbody>
                {entry.lines.map((l) => (
                  <tr key={l.id} className="border-t border-[var(--color-border)]">
                    <td className="py-2 px-3 text-[var(--color-text-muted)]">{l.line_number}</td>
                    <td className="py-2 px-3">
                      <span className="font-mono text-xs text-[var(--color-text-muted)] mr-2">{l.account_code}</span>
                      {l.account_name}
                    </td>
                    <td className="py-2 px-3 text-[var(--color-text-muted)]">{l.description || '—'}</td>
                    <td className="py-2 px-3 text-right font-mono">
                      {l.debit_amount > 0 ? fmt(l.debit_amount) : '—'}
                    </td>
                    <td className="py-2 px-3 text-right font-mono">
                      {l.credit_amount > 0 ? fmt(l.credit_amount) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-[var(--color-border)] bg-[var(--color-surface)] font-medium">
                  <td colSpan={3} className="py-2 px-3 text-right text-xs uppercase text-[var(--color-text-muted)]">Totals</td>
                  <td className="py-2 px-3 text-right font-mono">{fmt(entry.total_debits)}</td>
                  <td className="py-2 px-3 text-right font-mono">{fmt(entry.total_credits)}</td>
                </tr>
              </tfoot>
            </table>
          </div>

          {/* Meta + Narrative */}
          {entry.narrative && (
            <p className="text-sm text-[var(--color-text-muted)] italic">"{entry.narrative}"</p>
          )}
          {entry.rejection_reason && (
            <p className="text-sm text-[var(--color-danger)]">
              Rejection reason: {entry.rejection_reason}
            </p>
          )}

          {/* Workflow actions */}
          <div className="flex items-center gap-3 flex-wrap">
            {actions.filter((a) => a.show).length > 0 && (
              <>
                {(entry.status === 'pending' || entry.status === 'posted') && (
                  <input
                    type="text"
                    placeholder={entry.status === 'pending' ? 'Rejection reason…' : 'Reversal reason…'}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    className="px-3 py-1.5 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] w-56"
                  />
                )}
                {actions
                  .filter((a) => a.show)
                  .map((a) => (
                    <Button
                      key={a.action}
                      variant={a.variant}
                      size="sm"
                      isLoading={acting}
                      disabled={
                        (a.action === 'reject' && !reason.trim()) ||
                        (a.action === 'reverse' && !reason.trim())
                      }
                      onClick={() => onAction(a.action, entry.id)}
                    >
                      {a.icon}
                      <span className="ml-1.5">{a.label}</span>
                    </Button>
                  ))}
              </>
            )}
          </div>
        </div>
      </td>
    </tr>
  );
}

/* ── main page ───────────────────────────────── */

export default function JournalEntries() {
  const [data, setData] = useState<PaginatedEntries>({ items: [], total: 0, page: 1, page_size: 20 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [statusTab, setStatusTab] = useState('All');
  const [searchQ, setSearchQ] = useState('');
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [accounts, setAccounts] = useState<GLAccount[]>([]);
  const [acting, setActing] = useState(false);

  const fetchEntries = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const params: Record<string, unknown> = { page, page_size: 20 };
      if (statusTab !== 'All') params.status = statusTab.toLowerCase();
      if (searchQ) params.q = searchQ;
      const { data: d } = await glApi.getEntries(params as Parameters<typeof glApi.getEntries>[0]);
      setData(d);
    } catch {
      setError('Failed to load journal entries');
    } finally {
      setLoading(false);
    }
  }, [page, statusTab, searchQ]);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  useEffect(() => {
    glApi.getAccounts().then(({ data: d }) => setAccounts(d)).catch(() => {});
  }, []);

  const totalPages = Math.ceil(data.total / data.page_size);

  const handleAction = async (action: string, id: number) => {
    setActing(true);
    try {
      if (action === 'submit') await glApi.submitEntry(id);
      else if (action === 'approve') await glApi.approveEntry(id);
      else if (action === 'post') await glApi.postEntry(id);
      else if (action === 'reject') {
        const input = document.querySelector<HTMLInputElement>('input[placeholder="Rejection reason…"]');
        await glApi.rejectEntry(id, input?.value ?? 'Rejected');
      } else if (action === 'reverse') {
        const input = document.querySelector<HTMLInputElement>('input[placeholder="Reversal reason…"]');
        await glApi.reverseEntry(id, { reason: input?.value ?? 'Reversed' });
      }
      await fetchEntries();
    } catch {
      // ignore
    } finally {
      setActing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-[var(--color-primary)]/10">
            <BookOpen size={22} className="text-[var(--color-primary)]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-text)]">Journal Entries</h1>
            <p className="text-sm text-[var(--color-text-muted)]">{data.total} entries total</p>
          </div>
        </div>
        <Button onClick={() => setModalOpen(true)}>
          <Plus size={16} className="mr-2" /> New Entry
        </Button>
      </div>

      {/* Status tabs + search */}
      <Card padding="sm">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-1 bg-[var(--color-surface-hover)]/50 rounded-lg p-1">
            {STATUS_TABS.map((tab) => (
              <button
                key={tab}
                onClick={() => { setStatusTab(tab); setPage(1); }}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  statusTab === tab
                    ? 'bg-[var(--color-primary)] text-white'
                    : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
          <div className="relative flex-1 min-w-[200px]">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
            <input
              type="text"
              placeholder="Search entries…"
              value={searchQ}
              onChange={(e) => { setSearchQ(e.target.value); setPage(1); }}
              className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            />
          </div>
        </div>
      </Card>

      {/* Table */}
      <Card padding="none">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-[var(--color-text-muted)]">
            <Loader2 size={24} className="animate-spin mr-3" /> Loading entries…
          </div>
        ) : error ? (
          <div className="flex items-center justify-center py-20 text-[var(--color-danger)]">
            <AlertCircle size={20} className="mr-2" /> {error}
          </div>
        ) : data.items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-[var(--color-text-muted)]">
            <FileText size={40} className="mb-3 opacity-40" />
            <p className="text-lg font-medium">No entries found</p>
            <p className="text-sm mt-1">Create your first journal entry to get started.</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] text-xs uppercase tracking-wider">
                    <th className="py-3 px-4 w-8" />
                    <th className="py-3 px-3 text-left font-medium">Entry #</th>
                    <th className="py-3 px-3 text-left font-medium">Date</th>
                    <th className="py-3 px-3 text-left font-medium">Source</th>
                    <th className="py-3 px-3 text-left font-medium">Description</th>
                    <th className="py-3 px-3 text-right font-medium">Amount</th>
                    <th className="py-3 px-3 text-center font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((entry) => (
                    <>
                      <tr
                        key={entry.id}
                        className={`border-b border-[var(--color-border)] cursor-pointer transition-colors ${
                          expandedId === entry.id ? 'bg-[var(--color-surface-hover)]' : 'hover:bg-[var(--color-surface-hover)]'
                        }`}
                        onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
                      >
                        <td className="py-3 px-4 text-[var(--color-text-muted)]">
                          {expandedId === entry.id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                        </td>
                        <td className="py-3 px-3 font-mono text-[var(--color-primary)] font-medium">
                          {entry.entry_number}
                        </td>
                        <td className="py-3 px-3 text-[var(--color-text-muted)]">
                          {fmtDate(entry.transaction_date)}
                        </td>
                        <td className="py-3 px-3 text-[var(--color-text-muted)] capitalize">
                          {entry.source_type.replace(/_/g, ' ')}
                        </td>
                        <td className="py-3 px-3 max-w-[240px] truncate">{entry.description}</td>
                        <td className="py-3 px-3 text-right font-mono">{fmt(entry.total_debits)}</td>
                        <td className="py-3 px-3 text-center">
                          <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium capitalize ${STATUS_STYLES[entry.status] ?? 'bg-gray-500/20 text-gray-400'}`}>
                            {entry.status}
                          </span>
                        </td>
                      </tr>
                      {expandedId === entry.id && (
                        <EntryDetail
                          key={`detail-${entry.id}`}
                          entry={entry}
                          onAction={handleAction}
                          acting={acting}
                        />
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--color-border)]">
                <p className="text-sm text-[var(--color-text-muted)]">
                  Page {page} of {totalPages} · {data.total} entries
                </p>
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                    Previous
                  </Button>
                  <Button variant="ghost" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>

      {/* New entry modal */}
      {modalOpen && (
        <NewEntryModal
          accounts={accounts}
          onClose={() => setModalOpen(false)}
          onCreated={() => { setModalOpen(false); fetchEntries(); }}
        />
      )}
    </div>
  );
}
