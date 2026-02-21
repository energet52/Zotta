import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BookMarked,
  Search,
  Loader2,
  AlertCircle,
  ArrowRight,
  Calendar,
  FileText,
} from 'lucide-react';
import Card from '../../../../components/ui/Card';
import Button from '../../../../components/ui/Button';
import {
  glApi,
  type GLAccount,
  type AccountLedger as AccountLedgerType,
} from '../../../../api/glApi';

/* ── helpers ─────────────────────────────────── */

const fmt = (n: number) =>
  n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });

/* ── main page ───────────────────────────────── */

export default function AccountLedger() {
  const navigate = useNavigate();

  const [accounts, setAccounts] = useState<GLAccount[]>([]);
  const [loadingAccounts, setLoadingAccounts] = useState(true);
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [ledger, setLedger] = useState<AccountLedgerType | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [searchQ, setSearchQ] = useState('');

  /* Load accounts */
  useEffect(() => {
    glApi
      .getAccounts({ status: 'active' })
      .then(({ data }) => setAccounts(data))
      .catch(() => {})
      .finally(() => setLoadingAccounts(false));
  }, []);

  /* Load ledger when account or filters change */
  const fetchLedger = useCallback(async () => {
    if (!selectedAccountId) return;
    try {
      setLoading(true);
      setError('');
      const params: Record<string, string> = {};
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const { data } = await glApi.getAccountLedger(selectedAccountId, params);
      setLedger(data);
    } catch {
      setError('Failed to load ledger');
    } finally {
      setLoading(false);
    }
  }, [selectedAccountId, dateFrom, dateTo]);

  useEffect(() => {
    fetchLedger();
  }, [fetchLedger]);

  const filteredTxns = ledger?.transactions.filter((t) => {
    if (!searchQ) return true;
    const q = searchQ.toLowerCase();
    return (
      t.entry_number.toLowerCase().includes(q) ||
      t.description.toLowerCase().includes(q) ||
      t.source_type.toLowerCase().includes(q)
    );
  });

  const sortedAccounts = [...accounts].sort((a, b) => a.account_code.localeCompare(b.account_code));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2.5 rounded-xl bg-[var(--color-primary)]/10">
          <BookMarked size={22} className="text-[var(--color-primary)]" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">Account Ledger</h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            View posted transactions and running balance for an account
          </p>
        </div>
      </div>

      {/* Account selector + date filters */}
      <Card padding="sm">
        <div className="flex flex-wrap items-end gap-4">
          {/* Account picker */}
          <div className="flex-1 min-w-0 sm:min-w-[260px]">
            <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">Account</label>
            {loadingAccounts ? (
              <div className="flex items-center gap-2 text-sm text-[var(--color-text-muted)] py-2">
                <Loader2 size={14} className="animate-spin" /> Loading accounts…
              </div>
            ) : (
              <select
                value={selectedAccountId ?? ''}
                onChange={(e) => {
                  const v = e.target.value;
                  setSelectedAccountId(v ? Number(v) : null);
                  setLedger(null);
                }}
                className="w-full px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              >
                <option value="">Select an account…</option>
                {sortedAccounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.account_code} — {a.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Date range */}
          <div className="flex items-end gap-3">
            <div>
              <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">From</label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">To</label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              />
            </div>
            {(dateFrom || dateTo) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => { setDateFrom(''); setDateTo(''); }}
              >
                Clear
              </Button>
            )}
          </div>
        </div>
      </Card>

      {/* Content */}
      {!selectedAccountId ? (
        <Card>
          <div className="flex flex-col items-center justify-center py-16 text-[var(--color-text-muted)]">
            <BookMarked size={48} className="mb-4 opacity-30" />
            <p className="text-lg font-medium">Select an Account</p>
            <p className="text-sm mt-1">Choose an account from the dropdown above to view its ledger.</p>
          </div>
        </Card>
      ) : loading ? (
        <Card>
          <div className="flex items-center justify-center py-16 text-[var(--color-text-muted)]">
            <Loader2 size={24} className="animate-spin mr-3" /> Loading ledger…
          </div>
        </Card>
      ) : error ? (
        <Card>
          <div className="flex items-center justify-center py-16 text-[var(--color-danger)]">
            <AlertCircle size={20} className="mr-2" /> {error}
          </div>
        </Card>
      ) : ledger ? (
        <>
          {/* Balance summary bar */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card padding="sm">
              <p className="text-xs uppercase tracking-wider text-[var(--color-text-muted)] mb-1">Opening Balance</p>
              <p className="text-xl font-bold font-mono text-[var(--color-text)]">{fmt(ledger.opening_balance)}</p>
            </Card>
            <Card padding="sm">
              <p className="text-xs uppercase tracking-wider text-[var(--color-text-muted)] mb-1">Closing Balance</p>
              <p className="text-xl font-bold font-mono text-[var(--color-primary)]">{fmt(ledger.closing_balance)}</p>
            </Card>
            <Card padding="sm">
              <p className="text-xs uppercase tracking-wider text-[var(--color-text-muted)] mb-1">Transactions</p>
              <p className="text-xl font-bold text-[var(--color-text)]">{ledger.transactions.length}</p>
            </Card>
          </div>

          {/* Search within ledger */}
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
            <input
              type="text"
              placeholder="Search transactions…"
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            />
          </div>

          {/* Transactions table */}
          <Card padding="none">
            {filteredTxns && filteredTxns.length > 0 ? (
              <div className="overflow-x-auto max-w-full">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] text-xs uppercase tracking-wider">
                      <th className="py-3 px-4 text-left font-medium">Date</th>
                      <th className="py-3 px-3 text-left font-medium">Entry #</th>
                      <th className="py-3 px-3 text-left font-medium">Description</th>
                      <th className="py-3 px-3 text-left font-medium">Source</th>
                      <th className="py-3 px-3 text-right font-medium">Debit</th>
                      <th className="py-3 px-3 text-right font-medium">Credit</th>
                      <th className="py-3 px-3 text-right font-medium">Running Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {/* Opening balance row */}
                    <tr className="border-b border-[var(--color-border)] bg-[var(--color-surface-hover)]/40 italic">
                      <td className="py-2.5 px-4 text-[var(--color-text-muted)]">—</td>
                      <td className="py-2.5 px-3 text-[var(--color-text-muted)]">—</td>
                      <td className="py-2.5 px-3 text-[var(--color-text-muted)]">Opening Balance</td>
                      <td className="py-2.5 px-3" />
                      <td className="py-2.5 px-3" />
                      <td className="py-2.5 px-3" />
                      <td className="py-2.5 px-3 text-right font-mono font-medium">{fmt(ledger.opening_balance)}</td>
                    </tr>

                    {filteredTxns.map((t, idx) => (
                      <tr
                        key={`${t.entry_id}-${idx}`}
                        className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors"
                      >
                        <td className="py-2.5 px-4 text-[var(--color-text-muted)]">
                          <div className="flex items-center gap-1.5">
                            <Calendar size={13} className="opacity-50" />
                            {fmtDate(t.date)}
                          </div>
                        </td>
                        <td className="py-2.5 px-3">
                          <button
                            onClick={() => navigate(`/backoffice/gl/entries?entry=${t.entry_id}`)}
                            className="font-mono text-[var(--color-primary)] hover:underline flex items-center gap-1"
                          >
                            {t.entry_number}
                            <ArrowRight size={12} className="opacity-50" />
                          </button>
                        </td>
                        <td className="py-2.5 px-3 max-w-[200px] truncate">{t.description}</td>
                        <td className="py-2.5 px-3 text-[var(--color-text-muted)] capitalize text-xs">
                          {t.source_type.replace(/_/g, ' ')}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono">
                          {t.debit > 0 ? (
                            <span className="text-blue-400">{fmt(t.debit)}</span>
                          ) : (
                            <span className="text-[var(--color-text-muted)]">—</span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono">
                          {t.credit > 0 ? (
                            <span className="text-amber-400">{fmt(t.credit)}</span>
                          ) : (
                            <span className="text-[var(--color-text-muted)]">—</span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono font-medium">
                          {fmt(t.running_balance)}
                        </td>
                      </tr>
                    ))}

                    {/* Closing balance row */}
                    <tr className="bg-[var(--color-surface-hover)]/40 font-medium italic">
                      <td className="py-2.5 px-4 text-[var(--color-text-muted)]">—</td>
                      <td className="py-2.5 px-3 text-[var(--color-text-muted)]">—</td>
                      <td className="py-2.5 px-3 text-[var(--color-text-muted)]">Closing Balance</td>
                      <td className="py-2.5 px-3" />
                      <td className="py-2.5 px-3" />
                      <td className="py-2.5 px-3" />
                      <td className="py-2.5 px-3 text-right font-mono text-[var(--color-primary)]">
                        {fmt(ledger.closing_balance)}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-[var(--color-text-muted)]">
                <FileText size={36} className="mb-3 opacity-40" />
                <p className="font-medium">No transactions found</p>
                <p className="text-sm mt-1">This account has no posted transactions in the selected period.</p>
              </div>
            )}
          </Card>
        </>
      ) : null}
    </div>
  );
}
