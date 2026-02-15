import { useEffect, useState, useCallback } from 'react';
import {
  LayoutDashboard,
  Loader2,
  AlertCircle,
  Landmark,
  TrendingUp,
  ChevronRight,
  BarChart3,
} from 'lucide-react';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';
import { Link } from 'react-router-dom';
import Card from '../../../../components/ui/Card';
import { glApi, type AccountingPeriod, type JournalEntry, type PaginatedEntries } from '../../../../api/glApi';

/* ── types ───────────────────────────────────── */

interface DashboardSummary {
  [code: string]:
    | { name: string; balance: number; debit_total: number; credit_total: number }
    | number;
}

/* ── helpers ─────────────────────────────────── */

const fmt = (n: number) =>
  n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// Placeholder 12‑month trend data for sparklines
const MOCK_TREND_DATA = [
  { month: 'Jan', loanPortfolio: 420000, interestIncome: 8500 },
  { month: 'Feb', loanPortfolio: 435000, interestIncome: 9100 },
  { month: 'Mar', loanPortfolio: 448000, interestIncome: 9200 },
  { month: 'Apr', loanPortfolio: 462000, interestIncome: 9600 },
  { month: 'May', loanPortfolio: 478000, interestIncome: 10100 },
  { month: 'Jun', loanPortfolio: 491000, interestIncome: 10400 },
  { month: 'Jul', loanPortfolio: 505000, interestIncome: 10800 },
  { month: 'Aug', loanPortfolio: 518000, interestIncome: 11000 },
  { month: 'Sep', loanPortfolio: 532000, interestIncome: 11400 },
  { month: 'Oct', loanPortfolio: 548000, interestIncome: 11800 },
  { month: 'Nov', loanPortfolio: 562000, interestIncome: 12100 },
  { month: 'Dec', loanPortfolio: 575000, interestIncome: 12500 },
];

const KEY_ACCOUNTS = [
  { code: '1-2000', label: 'Loan Portfolio', icon: Landmark },
  { code: '1-3000', label: 'Interest Receivable', icon: TrendingUp },
  { code: '1-1000', label: 'Cash & Bank', icon: Landmark },
  { code: '2-2000', label: 'Allowance for Loan Losses', icon: BarChart3 },
  { code: '4-1000', label: 'Interest Income', icon: TrendingUp },
  { code: '5-1000', label: 'Provision Expense', icon: BarChart3 },
] as const;

/* ── main page ───────────────────────────────── */

export default function GLDashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [recentEntries, setRecentEntries] = useState<JournalEntry[]>([]);
  const [periods, setPeriods] = useState<AccountingPeriod[]>([]);
  const [selectedPeriod, setSelectedPeriod] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const periodId = selectedPeriod ? Number(selectedPeriod) : undefined;
      const [summaryRes, entriesRes] = await Promise.all([
        glApi.getDashboardSummary(periodId),
        glApi.getEntries({
          period_id: periodId,
          page: 1,
          page_size: 10,
        }),
      ]);
      setSummary(summaryRes.data as DashboardSummary);
      setRecentEntries((entriesRes.data as PaginatedEntries).items);
    } catch {
      setError('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  }, [selectedPeriod]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    glApi.getPeriods().then(({ data }) => setPeriods(data)).catch(() => {});
  }, []);

  const draftCount = summary && typeof summary['entries_draft'] === 'number' ? (summary['entries_draft'] as number) : 0;
  const pendingCount = summary && typeof summary['entries_pending_approval'] === 'number' ? (summary['entries_pending_approval'] as number) : 0;
  const postedCount = summary && typeof summary['entries_posted'] === 'number' ? (summary['entries_posted'] as number) : 0;

  const getBalance = (code: string) => {
    const val = summary?.[code];
    if (val && typeof val === 'object' && 'balance' in val) return (val as { balance: number }).balance;
    return 0;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-[var(--color-primary)]/10">
            <LayoutDashboard size={22} className="text-[var(--color-primary)]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-text)]">GL Dashboard</h1>
            <p className="text-sm text-[var(--color-text-muted)]">Financial command center</p>
          </div>
        </div>

        <div className="min-w-[220px]">
          <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Period</label>
          <select
            value={selectedPeriod}
            onChange={(e) => setSelectedPeriod(e.target.value)}
            className="w-full px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
          >
            <option value="">Current (all time)</option>
            {periods.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <Card>
          <div className="flex items-center justify-center py-20 text-[var(--color-text-muted)]">
            <Loader2 size={24} className="animate-spin mr-3" /> Loading dashboard…
          </div>
        </Card>
      ) : error ? (
        <Card>
          <div className="flex items-center justify-center py-20 text-[var(--color-danger)]">
            <AlertCircle size={20} className="mr-2" /> {error}
          </div>
        </Card>
      ) : (
        <>
          {/* Balance cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            {KEY_ACCOUNTS.map(({ code, label, icon: Icon }) => (
              <Card key={code} padding="sm" className="hover:bg-[var(--color-surface-hover)] transition-colors">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">{label}</p>
                    <p className="mt-1 text-lg font-bold font-mono text-[var(--color-text)]">
                      {fmt(getBalance(code))}
                    </p>
                  </div>
                  <Icon size={20} className="text-[var(--color-primary)]/60" />
                </div>
              </Card>
            ))}
          </div>

          {/* Sparkline + Entry counts */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card padding="md" className="lg:col-span-2">
              <h2 className="text-sm font-semibold text-[var(--color-text)] mb-4">12‑Month Trend (Loan Portfolio & Interest Income)</h2>
              <div className="h-32">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={MOCK_TREND_DATA}>
                    <defs>
                      <linearGradient id="gradLoan" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.4} />
                        <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="gradIncome" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--color-success)" stopOpacity={0.4} />
                        <stop offset="100%" stopColor="var(--color-success)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area
                      type="monotone"
                      dataKey="loanPortfolio"
                      stroke="var(--color-primary)"
                      fill="url(#gradLoan)"
                      strokeWidth={1.5}
                    />
                    <Area
                      type="monotone"
                      dataKey="interestIncome"
                      stroke="var(--color-success)"
                      fill="url(#gradIncome)"
                      strokeWidth={1.5}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card padding="md">
              <h2 className="text-sm font-semibold text-[var(--color-text)] mb-4">Entries by Status</h2>
              <div className="space-y-3">
                <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-gray-500/10">
                  <span className="text-sm text-[var(--color-text-muted)]">Draft</span>
                  <span className="font-mono font-semibold text-[var(--color-text)]">{draftCount}</span>
                </div>
                <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-amber-500/10">
                  <span className="text-sm text-[var(--color-text-muted)]">Pending Approval</span>
                  <span className="font-mono font-semibold text-[var(--color-text)]">{pendingCount}</span>
                </div>
                <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-emerald-500/10">
                  <span className="text-sm text-[var(--color-text-muted)]">Posted</span>
                  <span className="font-mono font-semibold text-[var(--color-text)]">{postedCount}</span>
                </div>
              </div>
            </Card>
          </div>

          {/* Recent journal entries */}
          <Card padding="none">
            <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
              <h2 className="text-sm font-semibold text-[var(--color-text)]">Recent Journal Entries</h2>
              <Link
                to="/backoffice/gl/entries"
                className="text-sm text-[var(--color-primary)] hover:underline flex items-center gap-1"
              >
                View all <ChevronRight size={14} />
              </Link>
            </div>
            <div className="overflow-x-auto">
              {recentEntries.length === 0 ? (
                <div className="py-12 text-center text-[var(--color-text-muted)] text-sm">
                  No journal entries yet
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] text-xs uppercase tracking-wider">
                      <th className="py-3 px-4 text-left font-medium">Entry</th>
                      <th className="py-3 px-3 text-left font-medium">Date</th>
                      <th className="py-3 px-3 text-left font-medium">Description</th>
                      <th className="py-3 px-3 text-left font-medium">Status</th>
                      <th className="py-3 px-3 text-right font-medium">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentEntries.map((entry) => (
                      <tr
                        key={entry.id}
                        className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors"
                      >
                        <td className="py-2.5 px-4 font-mono text-xs text-[var(--color-primary)]">
                          <Link to={`/backoffice/gl/entries`} className="hover:underline">
                            {entry.entry_number}
                          </Link>
                        </td>
                        <td className="py-2.5 px-3 text-[var(--color-text-muted)]">
                          {new Date(entry.transaction_date).toLocaleDateString('en-US')}
                        </td>
                        <td className="py-2.5 px-3 text-[var(--color-text)] truncate max-w-[200px]">
                          {entry.description || '—'}
                        </td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`text-xs px-2 py-0.5 rounded-full capitalize ${
                              entry.status === 'posted'
                                ? 'bg-emerald-500/20 text-emerald-400'
                                : entry.status === 'draft'
                                  ? 'bg-gray-500/20 text-gray-400'
                                  : entry.status === 'pending_approval'
                                    ? 'bg-amber-500/20 text-amber-400'
                                    : 'bg-gray-500/20 text-gray-400'
                            }`}
                          >
                            {entry.status.replace('_', ' ')}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono">
                          {fmt(entry.total_debits)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
