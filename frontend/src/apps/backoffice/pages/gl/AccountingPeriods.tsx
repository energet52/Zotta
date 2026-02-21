import React, { useEffect, useState, useCallback } from 'react';
import {
  CalendarDays,
  Plus,
  X,
  Loader2,
  AlertCircle,
  Lock,
  Unlock,
  XCircle,
  Calendar,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import Card from '../../../../components/ui/Card';
import Button from '../../../../components/ui/Button';
import Input from '../../../../components/ui/Input';
import { glApi, type AccountingPeriod } from '../../../../api/glApi';

/* ── helpers ─────────────────────────────────── */

const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });

const STATUS_STYLES: Record<string, { badge: string; dot: string; label: string }> = {
  open:       { badge: 'bg-emerald-500/15 text-emerald-400 ring-emerald-500/30', dot: 'bg-emerald-400', label: 'Open' },
  soft_close: { badge: 'bg-yellow-500/15 text-yellow-400 ring-yellow-500/30', dot: 'bg-yellow-400', label: 'Soft Close' },
  closed:     { badge: 'bg-orange-500/15 text-orange-400 ring-orange-500/30', dot: 'bg-orange-400', label: 'Closed' },
  locked:     { badge: 'bg-red-500/15 text-red-400 ring-red-500/30', dot: 'bg-red-400', label: 'Locked' },
};

function getStatusInfo(status: string) {
  return STATUS_STYLES[status] ?? STATUS_STYLES['open'];
}

/* ── create fiscal year modal ────────────────── */

function CreateYearModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [year, setYear] = useState(new Date().getFullYear() + 1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      await glApi.createFiscalYear(year);
      onCreated();
    } catch {
      setError('Failed to create fiscal year. It may already exist.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <Card className="w-full max-w-md mx-4 shadow-2xl" padding="lg">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-[var(--color-text)]">Create Fiscal Year</h2>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Fiscal Year"
            type="number"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            min={2020}
            max={2099}
            required
            helperText="This will create 12 monthly periods for the selected year."
          />

          {error && (
            <p className="text-sm text-[var(--color-danger)] flex items-center gap-1">
              <AlertCircle size={14} /> {error}
            </p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" type="button" onClick={onClose}>Cancel</Button>
            <Button type="submit" isLoading={saving}>
              <Plus size={16} className="mr-2" /> Create Year
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

/* ── main page ───────────────────────────────── */

export default function AccountingPeriods() {
  const [periods, setPeriods] = useState<AccountingPeriod[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [acting, setActing] = useState<number | null>(null);
  const [expandedYears, setExpandedYears] = useState<Set<number>>(new Set());

  const fetchPeriods = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const { data } = await glApi.getPeriods();
      setPeriods(data);
    } catch {
      setError('Failed to load accounting periods');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPeriods();
  }, [fetchPeriods]);

  /* Group by fiscal year */
  const grouped = periods.reduce<Record<number, AccountingPeriod[]>>((acc, p) => {
    if (!acc[p.fiscal_year]) acc[p.fiscal_year] = [];
    acc[p.fiscal_year].push(p);
    return acc;
  }, {});

  const sortedYears = Object.keys(grouped)
    .map(Number)
    .sort((a, b) => b - a);

  /* Auto-expand all years on load */
  useEffect(() => {
    if (sortedYears.length > 0 && expandedYears.size === 0) {
      setExpandedYears(new Set(sortedYears));
    }
  }, [sortedYears.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleYear = (y: number) => {
    setExpandedYears((prev) => {
      const next = new Set(prev);
      if (next.has(y)) next.delete(y);
      else next.add(y);
      return next;
    });
  };

  /* Period actions */
  const handleAction = async (id: number, action: 'close' | 'soft_close' | 'lock' | 'reopen') => {
    setActing(id);
    try {
      if (action === 'close') await glApi.closePeriod(id);
      else if (action === 'soft_close') await glApi.softClosePeriod(id);
      else if (action === 'lock') await glApi.lockPeriod(id);
      else if (action === 'reopen') await glApi.reopenPeriod(id);
      await fetchPeriods();
    } catch {
      // ignore
    } finally {
      setActing(null);
    }
  };

  const getActions = (p: AccountingPeriod): { label: string; action: 'close' | 'soft_close' | 'lock' | 'reopen'; variant: 'warning' | 'danger' | 'secondary' | 'success'; icon: React.ReactNode }[] => {
    switch (p.status) {
      case 'open':
        return [
          { label: 'Soft Close', action: 'soft_close', variant: 'warning', icon: <XCircle size={14} /> },
          { label: 'Close', action: 'close', variant: 'danger', icon: <Lock size={14} /> },
        ];
      case 'soft_close':
        return [
          { label: 'Close', action: 'close', variant: 'danger', icon: <Lock size={14} /> },
          { label: 'Reopen', action: 'reopen', variant: 'success', icon: <Unlock size={14} /> },
        ];
      case 'closed':
        return [
          { label: 'Lock', action: 'lock', variant: 'danger', icon: <Lock size={14} /> },
          { label: 'Reopen', action: 'reopen', variant: 'success', icon: <Unlock size={14} /> },
        ];
      case 'locked':
        return [
          { label: 'Reopen', action: 'reopen', variant: 'success', icon: <Unlock size={14} /> },
        ];
      default:
        return [];
    }
  };

  /* Summary stats */
  const stats = {
    open: periods.filter((p) => p.status === 'open').length,
    softClose: periods.filter((p) => p.status === 'soft_close').length,
    closed: periods.filter((p) => p.status === 'closed').length,
    locked: periods.filter((p) => p.status === 'locked').length,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-[var(--color-primary)]/10">
            <CalendarDays size={22} className="text-[var(--color-primary)]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-text)]">Accounting Periods</h1>
            <p className="text-sm text-[var(--color-text-muted)]">
              {periods.length} period{periods.length !== 1 ? 's' : ''} across {sortedYears.length} fiscal year{sortedYears.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
        <Button onClick={() => setModalOpen(true)}>
          <Plus size={16} className="mr-2" /> Create Fiscal Year
        </Button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: 'Open', value: stats.open, color: 'emerald' },
          { label: 'Soft Close', value: stats.softClose, color: 'yellow' },
          { label: 'Closed', value: stats.closed, color: 'orange' },
          { label: 'Locked', value: stats.locked, color: 'red' },
        ].map((s) => (
          <Card key={s.label} padding="sm">
            <div className="flex items-center gap-3">
              <div className={`w-2 h-8 rounded-full bg-${s.color}-500`} />
              <div>
                <p className="text-xs uppercase tracking-wider text-[var(--color-text-muted)]">{s.label}</p>
                <p className="text-xl font-bold text-[var(--color-text)]">{s.value}</p>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <Card>
          <div className="flex items-center justify-center py-20 text-[var(--color-text-muted)]">
            <Loader2 size={24} className="animate-spin mr-3" /> Loading periods…
          </div>
        </Card>
      ) : error ? (
        <Card>
          <div className="flex items-center justify-center py-20 text-[var(--color-danger)]">
            <AlertCircle size={20} className="mr-2" /> {error}
          </div>
        </Card>
      ) : periods.length === 0 ? (
        <Card>
          <div className="flex flex-col items-center justify-center py-20 text-[var(--color-text-muted)]">
            <CalendarDays size={40} className="mb-3 opacity-40" />
            <p className="text-lg font-medium">No Periods</p>
            <p className="text-sm mt-1">Create a fiscal year to generate accounting periods.</p>
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {sortedYears.map((year) => {
            const yearPeriods = grouped[year].sort((a, b) => a.period_number - b.period_number);
            const isOpen = expandedYears.has(year);
            const openCount = yearPeriods.filter((p) => p.status === 'open').length;
            const lockedCount = yearPeriods.filter((p) => p.status === 'locked').length;

            return (
              <Card key={year} padding="none">
                {/* Year header */}
                <button
                  onClick={() => toggleYear(year)}
                  className="w-full flex items-center justify-between px-4 sm:px-6 py-4 hover:bg-[var(--color-surface-hover)] transition-colors"
                >
                  <div className="flex items-center gap-3">
                    {isOpen ? (
                      <ChevronDown size={18} className="text-[var(--color-text-muted)]" />
                    ) : (
                      <ChevronRight size={18} className="text-[var(--color-text-muted)]" />
                    )}
                    <Calendar size={18} className="text-[var(--color-primary)]" />
                    <span className="text-lg font-bold text-[var(--color-text)]">FY {year}</span>
                    <span className="text-sm text-[var(--color-text-muted)]">
                      · {yearPeriods.length} periods
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    {openCount > 0 && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400">
                        {openCount} open
                      </span>
                    )}
                    {lockedCount > 0 && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/15 text-red-400">
                        {lockedCount} locked
                      </span>
                    )}
                  </div>
                </button>

                {/* Periods list */}
                {isOpen && (
                  <div className="border-t border-[var(--color-border)]">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] text-xs uppercase tracking-wider">
                          <th className="py-2.5 px-4 sm:px-6 text-left font-medium">Period</th>
                          <th className="py-2.5 px-3 text-left font-medium">Date Range</th>
                          <th className="py-2.5 px-3 text-center font-medium">Status</th>
                          <th className="py-2.5 px-3 text-right font-medium">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {yearPeriods.map((p) => {
                          const si = getStatusInfo(p.status);
                          const actions = getActions(p);

                          return (
                            <tr
                              key={p.id}
                              className="border-b border-[var(--color-border)] last:border-b-0 hover:bg-[var(--color-surface-hover)] transition-colors group"
                            >
                              <td className="py-3 px-4 sm:px-6">
                                <div className="flex items-center gap-2">
                                  <div className={`w-1.5 h-1.5 rounded-full ${si.dot}`} />
                                  <span className="font-medium text-[var(--color-text)]">{p.name}</span>
                                </div>
                              </td>
                              <td className="py-3 px-3 text-[var(--color-text-muted)]">
                                {fmtDate(p.start_date)} — {fmtDate(p.end_date)}
                              </td>
                              <td className="py-3 px-3 text-center">
                                <span className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full font-medium ring-1 ${si.badge}`}>
                                  {si.label}
                                </span>
                              </td>
                              <td className="py-3 px-3">
                                <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                  {actions.map((a) => (
                                    <Button
                                      key={a.action}
                                      variant={a.variant}
                                      size="sm"
                                      isLoading={acting === p.id}
                                      onClick={() => handleAction(p.id, a.action)}
                                    >
                                      {a.icon}
                                      <span className="ml-1">{a.label}</span>
                                    </Button>
                                  ))}
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {/* Create fiscal year modal */}
      {modalOpen && (
        <CreateYearModal
          onClose={() => setModalOpen(false)}
          onCreated={() => { setModalOpen(false); fetchPeriods(); }}
        />
      )}
    </div>
  );
}
