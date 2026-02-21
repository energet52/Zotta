import React, { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import {
  GitBranch,
  Plus,
  ChevronDown,
  ChevronRight,
  X,
  Loader2,
  AlertCircle,
  Trash2,
  Play,
  FileText,
} from 'lucide-react';
import api from '../../../../api/client';
import { glApi, type GLAccount } from '../../../../api/glApi';
import Card from '../../../../components/ui/Card';
import Button from '../../../../components/ui/Button';
import Input from '../../../../components/ui/Input';

/* ── types ───────────────────────────────────── */

interface MappingLine {
  id: number;
  line_type: string;
  gl_account_id: number;
  amount_source: string;
  description_template?: string;
  account_code?: string;
  account_name?: string;
}

interface MappingTemplate {
  id: number;
  name: string;
  event_type: string;
  credit_product_id?: number;
  is_active: boolean;
  conditions?: Record<string, unknown>;
  description?: string;
  lines: MappingLine[];
}

const EVENT_TYPES = [
  'loan_disbursement',
  'repayment',
  'interest_accrual',
  'fee',
  'provision',
  'write_off',
  'recovery',
  'reversal',
  'adjustment',
  'system',
  'manual',
] as const;

const AMOUNT_SOURCES = [
  { value: 'principal', label: 'Principal' },
  { value: 'interest', label: 'Interest' },
  { value: 'fee', label: 'Fee' },
  { value: 'full_amount', label: 'Full Amount' },
  { value: 'custom', label: 'Custom' },
] as const;

const EVENT_COLORS: Record<string, string> = {
  loan_disbursement: 'bg-sky-500/20 text-sky-400',
  repayment: 'bg-emerald-500/20 text-emerald-400',
  interest_accrual: 'bg-amber-500/20 text-amber-400',
  fee: 'bg-purple-500/20 text-purple-400',
  provision: 'bg-orange-500/20 text-orange-400',
  write_off: 'bg-red-500/20 text-red-400',
  recovery: 'bg-teal-500/20 text-teal-400',
  reversal: 'bg-pink-500/20 text-pink-400',
  adjustment: 'bg-indigo-500/20 text-indigo-400',
  system: 'bg-gray-500/20 text-gray-400',
  manual: 'bg-slate-500/20 text-slate-400',
};

const fmt = (n: number) =>
  n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const fmtEventType = (s: string) => s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

/* ── Create template modal ───────────────────── */

interface LineForm {
  key: number;
  line_type: string;
  gl_account_id: string;
  amount_source: string;
  description_template: string;
}

function CreateTemplateModal({
  accounts,
  onClose,
  onCreated,
}: {
  accounts: GLAccount[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState('');
  const [eventType, setEventType] = useState('loan_disbursement');
  const [productId, setProductId] = useState('');
  const [conditionsJson, setConditionsJson] = useState('{}');
  const [description, setDescription] = useState('');
  const [lines, setLines] = useState<LineForm[]>([
    { key: 1, line_type: 'debit', gl_account_id: '', amount_source: 'principal', description_template: '' },
    { key: 2, line_type: 'credit', gl_account_id: '', amount_source: 'principal', description_template: '' },
  ]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const nextKeyRef = useRef(3);

  const addLine = () => {
    const key = nextKeyRef.current++;
    setLines([
      ...lines,
      {
        key,
        line_type: 'debit',
        gl_account_id: '',
        amount_source: 'principal',
        description_template: '',
      },
    ]);
  };

  const removeLine = (key: number) => {
    if (lines.length <= 2) return;
    setLines(lines.filter((l) => l.key !== key));
  };

  const updateLine = (key: number, field: keyof LineForm, value: string) => {
    setLines(lines.map((l) => (l.key === key ? { ...l, [field]: value } : l)));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      let conditions: Record<string, unknown> | undefined;
      if (conditionsJson.trim()) {
        try {
          conditions = JSON.parse(conditionsJson) as Record<string, unknown>;
        } catch {
          setError('Conditions must be valid JSON');
          setSaving(false);
          return;
        }
      }

      const linesPayload = lines
        .filter((l) => l.gl_account_id)
        .map((l) => ({
          line_type: l.line_type,
          gl_account_id: Number(l.gl_account_id),
          amount_source: l.amount_source,
          description_template: l.description_template || undefined,
        }));

      if (linesPayload.length < 2) {
        setError('At least 2 lines with accounts are required');
        setSaving(false);
        return;
      }

      await api.post('/gl/mappings', {
        name,
        event_type: eventType,
        credit_product_id: productId ? Number(productId) : undefined,
        conditions,
        description: description || undefined,
        lines: linesPayload,
      });
      onCreated();
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : 'Failed to create template';
      setError(typeof msg === 'string' ? msg : 'Failed to create template');
    } finally {
      setSaving(false);
    }
  };

  const sortedAccounts = useMemo(
    () =>
      [...accounts]
        .filter((a) => a.status === 'active')
        .sort((a, b) => a.account_code.localeCompare(b.account_code)),
    [accounts]
  );

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 backdrop-blur-sm overflow-y-auto py-8">
      <Card className="w-full max-w-3xl mx-4 shadow-2xl" padding="lg">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-[var(--color-text)]">Create Mapping Template</h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="Template Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="e.g. Standard Disbursement"
            />
            <div className="w-full">
              <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">Event Type</label>
              <select
                value={eventType}
                onChange={(e) => setEventType(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              >
                {EVENT_TYPES.map((evt) => (
                  <option key={evt} value={evt}>
                    {fmtEventType(evt)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="Credit Product ID (optional)"
              type="number"
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              placeholder="Leave empty for global template"
            />
            <div className="w-full">
              <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">Description</label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
                className="w-full px-3 py-2 border rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              />
            </div>
          </div>

          <div className="w-full">
            <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">Conditions (JSON)</label>
            <textarea
              value={conditionsJson}
              onChange={(e) => setConditionsJson(e.target.value)}
              rows={3}
              placeholder='{"days_past_due": {"&gt;": 90}}'
              className="w-full px-3 py-2 border rounded-lg text-sm font-mono bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] resize-none"
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
                    <th className="py-2 px-3 text-left font-medium">Type</th>
                    <th className="py-2 px-3 text-left font-medium">Account</th>
                    <th className="py-2 px-3 text-left font-medium">Amount Source</th>
                    <th className="py-2 px-3 text-left font-medium">Description Template</th>
                    <th className="py-2 px-3 w-10" />
                  </tr>
                </thead>
                <tbody>
                  {lines.map((line) => (
                    <tr key={line.key} className="border-b border-[var(--color-border)] last:border-b-0">
                      <td className="py-2 px-3">
                        <select
                          value={line.line_type}
                          onChange={(e) => updateLine(line.key, 'line_type', e.target.value)}
                          className="w-full px-2 py-1.5 text-sm rounded border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                        >
                          <option value="debit">Debit</option>
                          <option value="credit">Credit</option>
                        </select>
                      </td>
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
                        <select
                          value={line.amount_source}
                          onChange={(e) => updateLine(line.key, 'amount_source', e.target.value)}
                          className="w-full px-2 py-1.5 text-sm rounded border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                        >
                          {AMOUNT_SOURCES.map((src) => (
                            <option key={src.value} value={src.value}>
                              {src.label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="py-2 px-3">
                        <input
                          type="text"
                          value={line.description_template}
                          onChange={(e) => updateLine(line.key, 'description_template', e.target.value)}
                          placeholder="{source_reference}, {amount}"
                          className="w-full px-2 py-1.5 text-sm rounded border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                        />
                      </td>
                      <td className="py-2 px-3">
                        <button
                          type="button"
                          onClick={() => removeLine(line.key)}
                          disabled={lines.length <= 2}
                          className="p-1 rounded hover:bg-red-500/10 text-[var(--color-text-muted)] hover:text-[var(--color-danger)] disabled:opacity-30"
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {error && (
            <p className="text-sm text-[var(--color-danger)] flex items-center gap-1">
              <AlertCircle size={14} /> {error}
            </p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" isLoading={saving}>
              <Plus size={16} className="mr-2" /> Create Template
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

/* ── Dry-run preview section ─────────────────── */

function DryRunPreview({ accountMap }: { accountMap: Map<number, GLAccount> }) {
  const [eventType, setEventType] = useState('loan_disbursement');
  const [principal, setPrincipal] = useState('1000');
  const [interest, setInterest] = useState('50');
  const [fee, setFee] = useState('25');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    template_name?: string;
    event_type?: string;
    description?: string;
    lines?: { gl_account_id: number; debit_amount: number; credit_amount: number; description?: string }[];
    total_debit?: number;
    total_credit?: number;
    is_balanced?: boolean;
    error?: string;
  } | null>(null);

  const runDryRun = async () => {
    setLoading(true);
    setResult(null);
    try {
      const amountBreakdown: Record<string, number> = {
        principal: parseFloat(principal) || 0,
        interest: parseFloat(interest) || 0,
        fee: parseFloat(fee) || 0,
        full_amount:
          (parseFloat(principal) || 0) + (parseFloat(interest) || 0) + (parseFloat(fee) || 0),
      };
      const { data } = await api.post('/gl/mappings/dry-run', {
        event_type: eventType,
        source_reference: 'DRY-RUN-TEST',
        amount_breakdown: amountBreakdown,
      });
      setResult(data);
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : 'Dry-run failed';
      setResult({ error: typeof msg === 'string' ? msg : 'Dry-run failed' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-2">
        <Play size={18} className="text-[var(--color-primary)]" />
        <h3 className="text-sm font-semibold text-[var(--color-text)]">Dry-Run Preview</h3>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        <div className="w-full">
          <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Event Type</label>
          <select
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
            className="w-full px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          >
            {EVENT_TYPES.map((evt) => (
              <option key={evt} value={evt}>
                {fmtEventType(evt)}
              </option>
            ))}
          </select>
        </div>
        <Input
          label="Principal"
          type="number"
          step="0.01"
          value={principal}
          onChange={(e) => setPrincipal(e.target.value)}
        />
        <Input
          label="Interest"
          type="number"
          step="0.01"
          value={interest}
          onChange={(e) => setInterest(e.target.value)}
        />
        <Input
          label="Fee"
          type="number"
          step="0.01"
          value={fee}
          onChange={(e) => setFee(e.target.value)}
        />
      </div>

      <Button type="button" variant="outline" size="sm" onClick={runDryRun} isLoading={loading}>
        <Play size={14} className="mr-2" /> Preview JE
      </Button>

      {result && (
        <Card padding="sm">
          {result.error ? (
            <p className="text-sm text-[var(--color-danger)] flex items-center gap-1">
              <AlertCircle size={14} /> {result.error}
            </p>
          ) : (
            <div className="space-y-2">
              <p className="text-sm text-[var(--color-text-muted)]">
                Template: <span className="text-[var(--color-text)] font-medium">{result.template_name}</span>
                {result.description && ` · ${result.description}`}
              </p>
              {result.lines && result.lines.length > 0 && (
                <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] text-xs uppercase tracking-wider bg-[var(--color-surface-hover)]/50">
                        <th className="py-2 px-3 text-left font-medium">Account</th>
                        <th className="py-2 px-3 text-left font-medium">Description</th>
                        <th className="py-2 px-3 text-right font-medium">Debit</th>
                        <th className="py-2 px-3 text-right font-medium">Credit</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.lines.map((ln, idx) => {
                        const acct = accountMap.get(ln.gl_account_id);
                        return (
                          <tr key={idx} className="border-b border-[var(--color-border)] last:border-b-0">
                            <td className="py-2 px-3">
                              <span className="font-mono text-xs text-[var(--color-text-muted)] mr-2">
                                {acct?.account_code ?? ln.gl_account_id}
                              </span>
                              {acct?.name ?? `Account ${ln.gl_account_id}`}
                            </td>
                            <td className="py-2 px-3 text-[var(--color-text-muted)]">
                              {ln.description ?? '—'}
                            </td>
                            <td className="py-2 px-3 text-right font-mono">
                              {ln.debit_amount > 0 ? fmt(ln.debit_amount) : '—'}
                            </td>
                            <td className="py-2 px-3 text-right font-mono">
                              {ln.credit_amount > 0 ? fmt(ln.credit_amount) : '—'}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                    <tfoot>
                      <tr className="border-t border-[var(--color-border)] bg-[var(--color-surface-hover)]/50 font-medium">
                        <td colSpan={2} className="py-2 px-3 text-right text-xs uppercase text-[var(--color-text-muted)]">
                          Totals
                        </td>
                        <td className="py-2 px-3 text-right font-mono">
                          {result.total_debit != null ? fmt(result.total_debit) : '—'}
                        </td>
                        <td className="py-2 px-3 text-right font-mono">
                          {result.total_credit != null ? fmt(result.total_credit) : '—'}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              )}
              {result.is_balanced != null && (
                <p
                  className={`text-xs ${
                    result.is_balanced ? 'text-[var(--color-success)]' : 'text-[var(--color-warning)]'
                  }`}
                >
                  {result.is_balanced ? 'Balanced' : 'Imbalanced'}
                </p>
              )}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

/* ── main page ───────────────────────────────── */

export default function GLMappings() {
  const [templates, setTemplates] = useState<MappingTemplate[]>([]);
  const [accounts, setAccounts] = useState<GLAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [eventFilter, setEventFilter] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [showDryRun, setShowDryRun] = useState(false);

  const accountMap = useMemo(() => {
    const m = new Map<number, GLAccount>();
    accounts.forEach((a) => m.set(a.id, a));
    return m;
  }, [accounts]);

  const fetchTemplates = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const params = eventFilter ? { event_type: eventFilter } : {};
      const { data } = await api.get<MappingTemplate[]>('/gl/mappings', { params });
      setTemplates(data);
    } catch {
      setError('Failed to load mapping templates');
    } finally {
      setLoading(false);
    }
  }, [eventFilter]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  useEffect(() => {
    glApi.getAccounts().then(({ data }) => setAccounts(data)).catch(() => {});
  }, []);

  const groupedByEvent = useMemo(() => {
    const groups: Record<string, MappingTemplate[]> = {};
    templates.forEach((t) => {
      const key = t.event_type;
      if (!groups[key]) groups[key] = [];
      groups[key].push(t);
    });
    return groups;
  }, [templates]);

  const displayTemplates = eventFilter
    ? (groupedByEvent[eventFilter] ?? [])
    : templates;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-[var(--color-primary)]/10">
            <GitBranch size={22} className="text-[var(--color-primary)]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-text)]">GL Mapping Templates</h1>
            <p className="text-sm text-[var(--color-text-muted)]">
              {templates.length} template{templates.length !== 1 ? 's' : ''} configured
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowDryRun(!showDryRun)}>
            <Play size={14} className="mr-2" />
            {showDryRun ? 'Hide' : 'Dry Run'}
          </Button>
          <Button onClick={() => setModalOpen(true)}>
            <Plus size={16} className="mr-2" /> New Template
          </Button>
        </div>
      </div>

      {/* Dry-run section */}
      {showDryRun && (
        <Card padding="md">
          <DryRunPreview accountMap={accountMap} />
        </Card>
      )}

      {/* Filters */}
      <Card padding="sm">
        <div className="flex flex-wrap items-center gap-3">
          <div className="w-full md:w-48">
            <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Event Type</label>
            <select
              value={eventFilter}
              onChange={(e) => setEventFilter(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            >
              <option value="">All event types</option>
              {EVENT_TYPES.map((evt) => (
                <option key={evt} value={evt}>
                  {fmtEventType(evt)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      {/* Table */}
      <Card padding="none">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-[var(--color-text-muted)]">
            <Loader2 size={24} className="animate-spin mr-3" />
            Loading templates…
          </div>
        ) : error ? (
          <div className="flex items-center justify-center py-20 text-[var(--color-danger)]">
            <AlertCircle size={20} className="mr-2" />
            {error}
          </div>
        ) : displayTemplates.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-[var(--color-text-muted)]">
            <FileText size={40} className="mb-3 opacity-40" />
            <p className="text-lg font-medium">No mapping templates found</p>
            <p className="text-sm mt-1">Create your first template to map loan events to journal entries.</p>
          </div>
        ) : (
          <div className="overflow-x-auto max-w-full">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] text-xs uppercase tracking-wider">
                  <th className="py-3 px-4 w-8" />
                  <th className="py-3 px-3 text-left font-medium">Name</th>
                  <th className="py-3 px-3 text-left font-medium">Event</th>
                  <th className="py-3 px-3 text-left font-medium">Product</th>
                  <th className="py-3 px-3 text-center font-medium">Active</th>
                  <th className="py-3 px-3 text-right font-medium">Lines</th>
                </tr>
              </thead>
              <tbody>
                {displayTemplates.map((tpl) => {
                  const isExpanded = expandedId === tpl.id;
                  return (
                    <React.Fragment key={tpl.id}>
                      <tr
                        key={tpl.id}
                        className={`border-b border-[var(--color-border)] cursor-pointer transition-colors ${
                          isExpanded ? 'bg-[var(--color-surface-hover)]' : 'hover:bg-[var(--color-surface-hover)]'
                        }`}
                        onClick={() => setExpandedId(isExpanded ? null : tpl.id)}
                      >
                        <td className="py-3 px-4 text-[var(--color-text-muted)]">
                          {isExpanded ? (
                            <ChevronDown size={16} />
                          ) : (
                            <ChevronRight size={16} />
                          )}
                        </td>
                        <td className="py-3 px-3 font-medium text-[var(--color-text)]">{tpl.name}</td>
                        <td className="py-3 px-3">
                          <span
                            className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                              EVENT_COLORS[tpl.event_type] ?? 'bg-gray-500/20 text-gray-400'
                            }`}
                          >
                            {fmtEventType(tpl.event_type)}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-[var(--color-text-muted)]">
                          {tpl.credit_product_id ?? '—'}
                        </td>
                        <td className="py-3 px-3 text-center">
                          <span
                            className={`text-xs px-2 py-0.5 rounded-full ${
                              tpl.is_active ? 'bg-[var(--color-success)]/20 text-[var(--color-success)]' : 'bg-[var(--color-text-muted)]/20 text-[var(--color-text-muted)]'
                            }`}
                          >
                            {tpl.is_active ? 'Yes' : 'No'}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-[var(--color-text-muted)]">
                          {tpl.lines.length}
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr>
                          <td colSpan={6} className="p-0">
                            <div className="bg-[var(--color-surface-hover)]/40 border-t border-[var(--color-border)] px-4 sm:px-6 py-4">
                              {tpl.description && (
                                <p className="text-sm text-[var(--color-text-muted)] mb-3">{tpl.description}</p>
                              )}
                              <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
                                <table className="w-full text-sm">
                                  <thead>
                                    <tr className="text-xs uppercase tracking-wider text-[var(--color-text-muted)] bg-[var(--color-surface)]">
                                      <th className="py-2 px-3 text-left font-medium">Type</th>
                                      <th className="py-2 px-3 text-left font-medium">Account</th>
                                      <th className="py-2 px-3 text-left font-medium">Amount Source</th>
                                      <th className="py-2 px-3 text-left font-medium">Description</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {tpl.lines.map((ln) => (
                                      <tr key={ln.id} className="border-t border-[var(--color-border)]">
                                        <td className="py-2 px-3">
                                          <span
                                            className={`text-xs px-2 py-0.5 rounded ${
                                              ln.line_type === 'debit'
                                                ? 'bg-blue-500/20 text-blue-400'
                                                : 'bg-emerald-500/20 text-emerald-400'
                                            }`}
                                          >
                                            {ln.line_type}
                                          </span>
                                        </td>
                                        <td className="py-2 px-3">
                                          <span className="font-mono text-xs text-[var(--color-text-muted)] mr-2">
                                            {ln.account_code ?? ln.gl_account_id}
                                          </span>
                                          {ln.account_name ?? `Account ${ln.gl_account_id}`}
                                        </td>
                                        <td className="py-2 px-3 text-[var(--color-text-muted)] capitalize">
                                          {ln.amount_source.replace(/_/g, ' ')}
                                        </td>
                                        <td className="py-2 px-3 text-[var(--color-text-muted)]">
                                          {ln.description_template ?? '—'}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Create modal */}
      {modalOpen && (
        <CreateTemplateModal
          accounts={accounts}
          onClose={() => setModalOpen(false)}
          onCreated={() => {
            setModalOpen(false);
            fetchTemplates();
          }}
        />
      )}
    </div>
  );
}
