import { useEffect, useState, useCallback } from 'react';
import {
  Scale,
  Loader2,
  AlertCircle,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import Card from '../../../../components/ui/Card';
import { glApi, type AccountingPeriod } from '../../../../api/glApi';
import api from '../../../../api/client';

/* ── types ───────────────────────────────────── */

interface BalanceSheetItem {
  account_id: number;
  account_code: string;
  account_name: string;
  level: number;
  balance: number;
}

interface BalanceSheetSection {
  items: BalanceSheetItem[];
  total: number;
}

interface BalanceSheetResponse {
  period_id?: number;
  as_of_date?: string;
  sections: {
    asset?: BalanceSheetSection;
    liability?: BalanceSheetSection;
    equity?: BalanceSheetSection;
  };
  assets_total: number;
  liabilities_equity_total: number;
  is_balanced: boolean;
}

/* ── helpers ─────────────────────────────────── */

const fmt = (n: number): string => {
  if (n < 0) return `(${Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })})`;
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const fmtClass = (n: number): string => (n < 0 ? 'text-[var(--color-danger)]' : '');

/* ── section row ─────────────────────────────── */

function SectionBlock({
  title,
  items,
  total,
  expanded,
  onToggle,
}: {
  title: string;
  items: BalanceSheetItem[];
  total: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="border-b border-[var(--color-border)] last:border-b-0">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 py-3 px-4 text-left hover:bg-[var(--color-surface-hover)] transition-colors"
      >
        {expanded ? (
          <ChevronDown size={18} className="text-[var(--color-text-muted)] shrink-0" />
        ) : (
          <ChevronRight size={18} className="text-[var(--color-text-muted)] shrink-0" />
        )}
        <span className="font-semibold text-[var(--color-text)] uppercase tracking-wider text-sm">{title}</span>
      </button>
      {expanded && (
        <>
          {items.map((row) => (
            <div
              key={row.account_id}
              className="flex items-center justify-between py-2 px-4 border-t border-[var(--color-border)]/50 hover:bg-[var(--color-surface-hover)]/50 transition-colors"
              style={{ paddingLeft: `${24 + row.level * 20}px` }}
            >
              <div className="flex items-center gap-3 min-w-0">
                <span className="font-mono text-xs text-[var(--color-text-muted)] shrink-0 w-20">{row.account_code}</span>
                <span className="text-sm text-[var(--color-text)] truncate">{row.account_name}</span>
              </div>
              <span className={`font-mono text-sm text-right tabular-nums shrink-0 ml-4 ${fmtClass(row.balance)}`}>
                {fmt(row.balance)}
              </span>
            </div>
          ))}
          <div
            className="flex items-center justify-between py-2.5 px-4 bg-[var(--color-surface-hover)]/50 border-t border-[var(--color-border)] font-medium"
            style={{ paddingLeft: `${24}px` }}
          >
            <span className="text-sm text-[var(--color-text)]">Total {title}</span>
            <span className={`font-mono text-sm text-right tabular-nums ${fmtClass(total)}`}>
              {fmt(total)}
            </span>
          </div>
        </>
      )}
    </div>
  );
}

/* ── main page ───────────────────────────────── */

export default function BalanceSheet() {
  const [data, setData] = useState<BalanceSheetResponse | null>(null);
  const [periods, setPeriods] = useState<AccountingPeriod[]>([]);
  const [selectedPeriod, setSelectedPeriod] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState<Record<string, boolean>>({
    asset: true,
    liability: true,
    equity: true,
  });

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const params: Record<string, string | number> = {};
      if (selectedPeriod) params.period_id = Number(selectedPeriod);
      const { data: res } = await api.get<BalanceSheetResponse>('/gl/balance-sheet', { params });
      setData(res);
    } catch {
      setError('Failed to load balance sheet');
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

  const toggleSection = (key: string) => {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-[var(--color-primary)]/10">
            <Scale size={22} className="text-[var(--color-primary)]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-text)]">Balance Sheet</h1>
            <p className="text-sm text-[var(--color-text-muted)]">
              Assets = Liabilities + Equity
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {data && (
            <div
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium ${
                data.is_balanced
                  ? 'bg-[var(--color-success)]/10 text-[var(--color-success)]'
                  : 'bg-[var(--color-danger)]/10 text-[var(--color-danger)]'
              }`}
            >
              {data.is_balanced ? (
                <>
                  <CheckCircle2 size={18} /> Balanced
                </>
              ) : (
                <>
                  <XCircle size={18} /> Unbalanced
                </>
              )}
            </div>
          )}
          <div className="min-w-0 sm:min-w-[220px]">
            <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Period</label>
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
        </div>
      </div>

      {loading ? (
        <Card>
          <div className="flex items-center justify-center py-20 text-[var(--color-text-muted)]">
            <Loader2 size={24} className="animate-spin mr-3" /> Loading balance sheet…
          </div>
        </Card>
      ) : error ? (
        <Card>
          <div className="flex items-center justify-center py-20 text-[var(--color-danger)]">
            <AlertCircle size={20} className="mr-2" /> {error}
          </div>
        </Card>
      ) : data ? (
        <Card padding="none">
          <div className="divide-y divide-[var(--color-border)]">
            <SectionBlock
              title="Assets"
              items={data.sections?.asset?.items ?? []}
              total={data.assets_total}
              expanded={expanded.asset ?? true}
              onToggle={() => toggleSection('asset')}
            />
            <SectionBlock
              title="Liabilities"
              items={data.sections?.liability?.items ?? []}
              total={data.sections?.liability?.total ?? 0}
              expanded={expanded.liability ?? true}
              onToggle={() => toggleSection('liability')}
            />
            <SectionBlock
              title="Equity"
              items={data.sections?.equity?.items ?? []}
              total={data.sections?.equity?.total ?? 0}
              expanded={expanded.equity ?? true}
              onToggle={() => toggleSection('equity')}
            />
          </div>

          {/* Grand total / Balance check */}
          <div className="border-t-2 border-[var(--color-border)] bg-[var(--color-surface-hover)]/60 px-4 py-4">
            <div className="flex justify-between items-center text-sm">
              <span className="font-semibold text-[var(--color-text)]">Assets Total</span>
              <span className={`font-mono tabular-nums ${fmtClass(data.assets_total)}`}>
                {fmt(data.assets_total)}
              </span>
            </div>
            <div className="flex justify-between items-center text-sm mt-1 text-[var(--color-text-muted)]">
              <span>Liabilities + Equity Total</span>
              <span className={`font-mono tabular-nums ${fmtClass(data.liabilities_equity_total)}`}>
                {fmt(data.liabilities_equity_total)}
              </span>
            </div>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
