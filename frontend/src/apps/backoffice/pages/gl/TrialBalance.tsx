import React, { useEffect, useState, useCallback } from 'react';
import {
  Scale,
  Loader2,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Filter,
} from 'lucide-react';
import Card from '../../../../components/ui/Card';
import Button from '../../../../components/ui/Button';
import {
  glApi,
  type TrialBalance as TrialBalanceType,
  type TrialBalanceRow,
  type AccountingPeriod,
} from '../../../../api/glApi';

/* ── helpers ─────────────────────────────────── */

const fmt = (n: number) =>
  n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const CATEGORY_COLORS: Record<string, { bg: string; text: string; bar: string }> = {
  Asset:     { bg: 'bg-blue-500/8',    text: 'text-blue-400',    bar: 'bg-blue-500' },
  Liability: { bg: 'bg-amber-500/8',   text: 'text-amber-400',   bar: 'bg-amber-500' },
  Equity:    { bg: 'bg-purple-500/8',  text: 'text-purple-400',  bar: 'bg-purple-500' },
  Revenue:   { bg: 'bg-emerald-500/8', text: 'text-emerald-400', bar: 'bg-emerald-500' },
  Expense:   { bg: 'bg-red-500/8',     text: 'text-red-400',     bar: 'bg-red-500' },
};

const LEVELS = [1, 2, 3, 4, 5];

/* ── main page ───────────────────────────────── */

export default function TrialBalance() {
  const [tb, setTb] = useState<TrialBalanceType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [periods, setPeriods] = useState<AccountingPeriod[]>([]);
  const [selectedPeriod, setSelectedPeriod] = useState<string>('');
  const [level, setLevel] = useState(5);

  /* Load periods */
  useEffect(() => {
    glApi.getPeriods().then(({ data }) => setPeriods(data)).catch(() => {});
  }, []);

  /* Load trial balance */
  const fetchTB = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const params: Record<string, unknown> = { level };
      if (selectedPeriod) params.period_id = Number(selectedPeriod);
      const { data } = await glApi.getTrialBalance(params as Parameters<typeof glApi.getTrialBalance>[0]);
      setTb(data);
    } catch {
      setError('Failed to load trial balance');
    } finally {
      setLoading(false);
    }
  }, [selectedPeriod, level]);

  useEffect(() => {
    fetchTB();
  }, [fetchTB]);

  /* Group rows by category for visual sections */
  const groupedRows = tb?.rows.reduce<Record<string, TrialBalanceRow[]>>((acc, row) => {
    const cat = row.account_category || 'Other';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(row);
    return acc;
  }, {});

  const categoryOrder = ['Asset', 'Liability', 'Equity', 'Revenue', 'Expense'];
  const sortedCategories = groupedRows
    ? categoryOrder.filter((c) => groupedRows[c]?.length)
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-[var(--color-primary)]/10">
            <Scale size={22} className="text-[var(--color-primary)]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-text)]">Trial Balance</h1>
            <p className="text-sm text-[var(--color-text-muted)]">
              {tb ? `${tb.rows.length} accounts` : 'Loading…'}
            </p>
          </div>
        </div>

        {/* Balanced indicator */}
        {tb && (
          <div
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium ${
              tb.is_balanced
                ? 'bg-emerald-500/10 text-emerald-400'
                : 'bg-red-500/10 text-red-400'
            }`}
          >
            {tb.is_balanced ? (
              <>
                <CheckCircle2 size={18} /> Balanced
              </>
            ) : (
              <>
                <XCircle size={18} /> Unbalanced — Difference: {fmt(Math.abs(tb.total_debits - tb.total_credits))}
              </>
            )}
          </div>
        )}
      </div>

      {/* Filters */}
      <Card padding="sm">
        <div className="flex flex-wrap items-end gap-4">
          <div className="min-w-0 sm:min-w-[200px]">
            <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">
              <Filter size={13} className="inline mr-1" /> Period
            </label>
            <select
              value={selectedPeriod}
              onChange={(e) => setSelectedPeriod(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            >
              <option value="">Current (all time)</option>
              {periods.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.start_date} to {p.end_date})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">Depth Level</label>
            <div className="flex items-center gap-1 bg-[var(--color-surface-hover)]/50 rounded-lg p-1">
              {LEVELS.map((l) => (
                <button
                  key={l}
                  onClick={() => setLevel(l)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    level === l
                      ? 'bg-[var(--color-primary)] text-white'
                      : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
                  }`}
                >
                  L{l}
                </button>
              ))}
            </div>
          </div>

          <Button variant="ghost" size="sm" onClick={fetchTB} className="ml-auto">
            Refresh
          </Button>
        </div>
      </Card>

      {/* Content */}
      {loading ? (
        <Card>
          <div className="flex items-center justify-center py-20 text-[var(--color-text-muted)]">
            <Loader2 size={24} className="animate-spin mr-3" /> Loading trial balance…
          </div>
        </Card>
      ) : error ? (
        <Card>
          <div className="flex items-center justify-center py-20 text-[var(--color-danger)]">
            <AlertCircle size={20} className="mr-2" /> {error}
          </div>
        </Card>
      ) : tb && tb.rows.length === 0 ? (
        <Card>
          <div className="flex flex-col items-center justify-center py-20 text-[var(--color-text-muted)]">
            <Scale size={40} className="mb-3 opacity-40" />
            <p className="text-lg font-medium">No Data</p>
            <p className="text-sm mt-1">No trial balance data available for the selected period.</p>
          </div>
        </Card>
      ) : tb ? (
        <Card padding="none">
          <div className="overflow-x-auto max-w-full">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] text-xs uppercase tracking-wider">
                  <th className="py-3 px-4 text-left font-medium w-24">Code</th>
                  <th className="py-3 px-3 text-left font-medium">Account Name</th>
                  <th className="py-3 px-3 text-left font-medium w-28">Category</th>
                  <th className="py-3 px-3 text-right font-medium w-36">Debit</th>
                  <th className="py-3 px-3 text-right font-medium w-36">Credit</th>
                </tr>
              </thead>
              <tbody>
                {sortedCategories.map((cat) => {
                  const colors = CATEGORY_COLORS[cat] ?? { bg: '', text: 'text-gray-400', bar: 'bg-gray-500' };
                  const rows = groupedRows![cat];
                  const catDebit = rows.reduce((s, r) => s + r.debit_balance, 0);
                  const catCredit = rows.reduce((s, r) => s + r.credit_balance, 0);

                  return (
                    <React.Fragment key={cat}>
                      {/* Category header */}
                      <tr className={`${colors.bg} border-b border-[var(--color-border)]`}>
                        <td colSpan={3} className="py-2.5 px-4">
                          <div className="flex items-center gap-2">
                            <div className={`w-1 h-4 rounded-full ${colors.bar}`} />
                            <span className={`text-xs font-semibold uppercase tracking-wider ${colors.text}`}>
                              {cat}
                            </span>
                            <span className="text-xs text-[var(--color-text-muted)]">
                              ({rows.length} account{rows.length !== 1 ? 's' : ''})
                            </span>
                          </div>
                        </td>
                        <td className={`py-2.5 px-3 text-right font-mono text-xs font-medium ${colors.text}`}>
                          {catDebit > 0 ? fmt(catDebit) : ''}
                        </td>
                        <td className={`py-2.5 px-3 text-right font-mono text-xs font-medium ${colors.text}`}>
                          {catCredit > 0 ? fmt(catCredit) : ''}
                        </td>
                      </tr>

                      {/* Account rows */}
                      {rows.map((row) => (
                        <tr
                          key={row.account_id}
                          className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors"
                        >
                          <td className="py-2.5 px-4 font-mono text-xs text-[var(--color-text-muted)]">
                            {row.account_code}
                          </td>
                          <td className="py-2.5 px-3" style={{ paddingLeft: `${(row.level - 1) * 16 + 12}px` }}>
                            {row.account_name}
                          </td>
                          <td className="py-2.5 px-3">
                            <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${colors.text} ${colors.bg}`}>
                              {row.account_category}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono">
                            {row.debit_balance > 0 ? (
                              <span>{fmt(row.debit_balance)}</span>
                            ) : (
                              <span className="text-[var(--color-text-muted)]">—</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono">
                            {row.credit_balance > 0 ? (
                              <span>{fmt(row.credit_balance)}</span>
                            ) : (
                              <span className="text-[var(--color-text-muted)]">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </React.Fragment>
                  );
                })}
              </tbody>

              {/* Totals footer */}
              <tfoot>
                <tr className="border-t-2 border-[var(--color-border)] bg-[var(--color-surface-hover)]/60 font-semibold">
                  <td className="py-3 px-4" />
                  <td className="py-3 px-3 text-right text-xs uppercase tracking-wider text-[var(--color-text-muted)]">
                    Grand Total
                  </td>
                  <td className="py-3 px-3" />
                  <td className="py-3 px-3 text-right font-mono text-base">{fmt(tb.total_debits)}</td>
                  <td className="py-3 px-3 text-right font-mono text-base">{fmt(tb.total_credits)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
