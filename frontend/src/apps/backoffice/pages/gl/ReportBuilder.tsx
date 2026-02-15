import { useEffect, useState, useCallback } from 'react';
import {
  Wrench,
  Loader2,
  AlertCircle,
  Download,
  Save,
  FolderOpen,
  Trash2,
  FileSpreadsheet,
  FileText,
  FileDown,
} from 'lucide-react';
import api from '../../../../api/client';
import { glApi, type GLAccount, type AccountingPeriod, type TrialBalanceRow } from '../../../../api/glApi';
import Card from '../../../../components/ui/Card';
import Button from '../../../../components/ui/Button';

/* ── Types ───────────────────────────────────────────────────────── */

const METRICS = [
  { id: 'debit_total', label: 'Debit Total' },
  { id: 'credit_total', label: 'Credit Total' },
  { id: 'net_balance', label: 'Net Balance' },
  { id: 'transaction_count', label: 'Transaction Count' },
] as const;

const GROUPINGS = [
  { id: 'account', label: 'Account' },
  { id: 'category', label: 'Category' },
  { id: 'period', label: 'Period' },
  { id: 'source_type', label: 'Source Type' },
] as const;

export interface ReportConfig {
  name: string;
  accountIds: number[];
  metrics: string[];
  grouping: string;
  periodId: string;
  dateFrom: string;
  dateTo: string;
}

export interface ReportRow {
  account_id: number;
  account_code: string;
  account_name: string;
  account_category: string;
  debit_total?: number;
  credit_total?: number;
  net_balance?: number;
  transaction_count?: number;
}

const TEMPLATE_STORAGE_KEY = 'gl_report_builder_templates';

/* ── Helpers ─────────────────────────────────────────────────────── */

const fmtNum = (n: number | undefined | null): string => {
  if (n == null) return '—';
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const escapeCsv = (val: unknown): string => {
  const s = String(val ?? '');
  if (s.includes(',') || s.includes('"') || s.includes('\n')) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
};

/* ── Main Page ───────────────────────────────────────────────────── */

export default function ReportBuilder() {
  const [accounts, setAccounts] = useState<GLAccount[]>([]);
  const [periods, setPeriods] = useState<AccountingPeriod[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [reportError, setReportError] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');

  const [reportName, setReportName] = useState('Custom Report');
  const [accountIds, setAccountIds] = useState<Set<number>>(new Set());
  const [metrics, setMetrics] = useState<Set<string>>(new Set(['debit_total', 'credit_total', 'net_balance']));
  const [grouping, setGrouping] = useState<string>('account');
  const [periodId, setPeriodId] = useState<string>('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const [reportRows, setReportRows] = useState<ReportRow[]>([]);
  const [templates, setTemplates] = useState<ReportConfig[]>([]);

  /* Load accounts and periods */
  useEffect(() => {
    Promise.all([
      glApi.getAccounts().then(({ data }) => setAccounts(data)),
      glApi.getPeriods().then(({ data }) => setPeriods(data)),
    ])
      .catch(() => setError('Failed to load accounts and periods'))
      .finally(() => setLoading(false));
  }, []);

  /* Load templates from localStorage */
  useEffect(() => {
    try {
      const raw = localStorage.getItem(TEMPLATE_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as ReportConfig[];
        if (Array.isArray(parsed)) setTemplates(parsed);
      }
    } catch {
      setTemplates([]);
    }
  }, []);

  const saveTemplate = useCallback(() => {
    const config: ReportConfig = {
      name: reportName,
      accountIds: Array.from(accountIds),
      metrics: Array.from(metrics),
      grouping,
      periodId,
      dateFrom,
      dateTo,
    };
    const next = [...templates.filter((t) => t.name !== config.name), config];
    setTemplates(next);
    localStorage.setItem(TEMPLATE_STORAGE_KEY, JSON.stringify(next));
  }, [reportName, accountIds, metrics, grouping, periodId, dateFrom, dateTo, templates]);

  const loadTemplate = useCallback((config: ReportConfig) => {
    setReportName(config.name);
    setAccountIds(new Set(config.accountIds));
    setMetrics(new Set(config.metrics));
    setGrouping(config.grouping);
    setPeriodId(config.periodId ?? '');
    setDateFrom(config.dateFrom ?? '');
    setDateTo(config.dateTo ?? '');
    setReportError('');
  }, []);

  const deleteTemplate = useCallback((name: string) => {
    const next = templates.filter((t) => t.name !== name);
    setTemplates(next);
    localStorage.setItem(TEMPLATE_STORAGE_KEY, JSON.stringify(next));
  }, [templates]);

  const toggleAccount = (id: number) => {
    setAccountIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAllAccounts = () => {
    const filtered = categoryFilter
      ? accounts.filter((a) => a.account_category === categoryFilter)
      : accounts;
    setAccountIds((prev) => {
      const next = new Set(prev);
      filtered.forEach((a) => next.add(a.id));
      return next;
    });
  };

  const clearAccounts = () => setAccountIds(new Set());

  const toggleMetric = (id: string) => {
    setMetrics((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const generateReport = useCallback(async () => {
    setReportError('');
    setGenerating(true);
    try {
      const params: { period_id?: number; as_of_date?: string } = {};
      if (periodId) params.period_id = Number(periodId);
      if (dateTo && !periodId) params.as_of_date = dateTo;

      const { data } = await glApi.getTrialBalance(params);
      const rawRows = (data.rows ?? []) as TrialBalanceRow[];
      const filtered = accountIds.size > 0
        ? rawRows.filter((r) => accountIds.has(r.account_id))
        : rawRows;
      const rows: ReportRow[] = filtered.map((r) => ({
        account_id: r.account_id,
        account_code: r.account_code,
        account_name: r.account_name,
        account_category: r.account_category,
        debit_total: r.debit_balance,
        credit_total: r.credit_balance,
        net_balance: r.debit_balance - r.credit_balance,
        transaction_count: undefined,
      }));
      setReportRows(rows);
    } catch {
      setReportError('Failed to generate report');
      setReportRows([]);
    } finally {
      setGenerating(false);
    }
  }, [accountIds, periodId, dateTo, accounts]);

  const exportCsv = useCallback(() => {
    if (reportRows.length === 0) return;
    const visibleCols =
      metrics.size > 0
        ? ['account_code', 'account_name', 'account_category', ...Array.from(metrics)]
        : ['account_code', 'account_name', 'account_category', 'debit_total', 'credit_total', 'net_balance'];

    const header = visibleCols.map((c) => c.replace(/_/g, ' ')).join(',');
    const body = reportRows
      .map((r) =>
        visibleCols
          .map((c) => escapeCsv((r as unknown as Record<string, unknown>)[c]))
          .join(',')
      )
      .join('\n');
    const csv = `${header}\n${body}`;
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${reportName.replace(/\s+/g, '_')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [reportRows, reportName, metrics]);

  const exportViaApi = useCallback(
    async (format: 'csv' | 'xlsx' | 'pdf') => {
      setExporting(format);
      try {
        const params: Record<string, unknown> = {};
        if (periodId) params.period_id = periodId;
        if (dateFrom) params.date_from = dateFrom;
        if (dateTo) params.date_to = dateTo;

        const { data } = await api.post(
          '/gl/export',
          {
            format,
            export_type: 'trial_balance',
            filters: params,
            title: reportName,
          },
          { responseType: 'blob' }
        );
        const blob = data as Blob;
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const ext = format === 'xlsx' ? 'xlsx' : format;
        a.download = `${reportName.replace(/\s+/g, '_')}.${ext}`;
        a.click();
        URL.revokeObjectURL(url);
      } catch {
        if (format === 'csv') exportCsv();
      } finally {
        setExporting(null);
      }
    },
    [reportName, periodId, dateFrom, dateTo, exportCsv]
  );

  const categories = Array.from(new Set(accounts.map((a) => a.account_category))).filter(Boolean).sort();
  const filteredAccounts = categoryFilter
    ? accounts.filter((a) => a.account_category === categoryFilter)
    : accounts;

  const displayedRows =
    grouping === 'category'
      ? (() => {
          const byCat = reportRows.reduce<Record<string, ReportRow[]>>((acc, r) => {
            const cat: string = r.account_category || 'Other';
            if (!acc[cat]) acc[cat] = [];
            acc[cat].push(r);
            return acc;
          }, {});
          const ordered = ['Asset', 'Liability', 'Equity', 'Revenue', 'Expense', 'Other'];
          const result: ReportRow[] = [];
          const allCats = [...ordered, ...Object.keys(byCat).filter((c: string) => !ordered.includes(c))];
          for (const cat of allCats) {
            const rows = byCat[cat];
            if (rows) result.push(...rows);
          }
          return result;
        })()
      : reportRows;

  const totals = reportRows.length
    ? reportRows.reduce(
        (acc, r) => ({
          debit_total: acc.debit_total + (r.debit_total ?? 0),
          credit_total: acc.credit_total + (r.credit_total ?? 0),
          net_balance: acc.net_balance + (r.net_balance ?? 0),
        }),
        { debit_total: 0, credit_total: 0, net_balance: 0 }
      )
    : null;

  return (
    <div className="space-y-4 h-[calc(100vh-8rem)]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-[var(--color-primary)]/10">
            <Wrench size={22} className="text-[var(--color-primary)]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-text)]">Report Builder</h1>
            <p className="text-sm text-[var(--color-text-muted)]">
              Build custom reports by selecting accounts, metrics, and time periods
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="flex items-center text-[var(--color-danger)]">
          <AlertCircle size={18} className="mr-2" /> {error}
        </div>
      )}

      <div className="flex gap-4 flex-1 min-h-0" style={{ height: 'calc(100% - 5rem)' }}>
        {/* Left: Configuration Panel (~40%) */}
        <div
          className="w-[40%] min-w-[320px] flex flex-col gap-3 shrink-0"
          style={{ maxHeight: '100%' }}
        >
          <Card padding="sm" className="flex flex-col gap-3 flex-1 min-h-0 overflow-hidden">
            <h2 className="text-sm font-semibold text-[var(--color-text)] uppercase tracking-wider">
              Report Configuration
            </h2>
            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Report Name</label>
              <input
                type="text"
                value={reportName}
                onChange={(e) => setReportName(e.target.value)}
                placeholder="Custom Report"
                className="w-full px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-xs font-medium text-[var(--color-text-muted)]">Accounts</label>
                <div className="flex gap-1">
                  <button
                    type="button"
                    onClick={selectAllAccounts}
                    className="text-xs text-[var(--color-primary)] hover:underline"
                  >
                    All
                  </button>
                  <span className="text-[var(--color-text-muted)]">|</span>
                  <button
                    type="button"
                    onClick={clearAccounts}
                    className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                  >
                    Clear
                  </button>
                </div>
              </div>
              {categories.length > 0 && (
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="w-full mb-2 px-2 py-1.5 text-xs rounded border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)]"
                >
                  <option value="">All categories</option>
                  {categories.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              )}
              <div className="border border-[var(--color-border)] rounded-lg overflow-hidden max-h-40 overflow-y-auto bg-[var(--color-surface)]">
                {filteredAccounts.map((a) => (
                  <label
                    key={a.id}
                    className="flex items-center gap-2 px-3 py-2 hover:bg-[var(--color-surface-hover)] cursor-pointer border-b border-[var(--color-border)] last:border-b-0"
                  >
                    <input
                      type="checkbox"
                      checked={accountIds.has(a.id)}
                      onChange={() => toggleAccount(a.id)}
                      className="rounded border-[var(--color-border)]"
                    />
                    <span className="text-sm text-[var(--color-text)] truncate">
                      {a.account_code} {a.name}
                    </span>
                  </label>
                ))}
                {filteredAccounts.length === 0 && (
                  <div className="px-3 py-4 text-sm text-[var(--color-text-muted)]">No accounts</div>
                )}
              </div>
              <p className="text-xs text-[var(--color-text-muted)] mt-1">
                {accountIds.size === 0 ? 'All accounts' : `${accountIds.size} selected`}
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Metrics</label>
              <div className="flex flex-wrap gap-2">
                {METRICS.map((m) => (
                  <label
                    key={m.id}
                    className="flex items-center gap-1.5 px-2 py-1.5 rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={metrics.has(m.id)}
                      onChange={() => toggleMetric(m.id)}
                      className="rounded"
                    />
                    <span className="text-xs text-[var(--color-text)]">{m.label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Grouping</label>
              <select
                value={grouping}
                onChange={(e) => setGrouping(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
              >
                {GROUPINGS.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Time Period</label>
              <select
                value={periodId}
                onChange={(e) => setPeriodId(e.target.value)}
                className="w-full mb-2 px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)]"
              >
                <option value="">Current (all time)</option>
                {periods.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <div className="flex gap-2">
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  placeholder="From"
                  className="flex-1 px-2 py-1.5 text-sm rounded border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)]"
                />
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  placeholder="To"
                  className="flex-1 px-2 py-1.5 text-sm rounded border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)]"
                />
              </div>
            </div>

            <Button
              variant="primary"
              size="sm"
              className="w-full"
              onClick={generateReport}
              isLoading={generating}
              disabled={generating || loading}
            >
              {generating ? (
                <Loader2 size={16} className="animate-spin mr-2" />
              ) : (
                <FileSpreadsheet size={16} className="mr-2" />
              )}
              Generate Report
            </Button>

            {templates.length > 0 && (
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">
                  Saved Templates
                </label>
                <div className="space-y-1 max-h-24 overflow-y-auto">
                  {templates.map((t) => (
                    <div
                      key={t.name}
                      className="flex items-center justify-between gap-2 px-2 py-1.5 rounded hover:bg-[var(--color-surface-hover)]"
                    >
                      <button
                        type="button"
                        onClick={() => loadTemplate(t)}
                        className="flex items-center gap-1 text-xs text-[var(--color-text)] hover:text-[var(--color-primary)] truncate flex-1 text-left"
                        title="Load template"
                      >
                        <FolderOpen size={12} />
                        {t.name}
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteTemplate(t.name)}
                        className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-danger)]"
                        title="Delete template"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  ))}
                </div>
                <Button variant="ghost" size="sm" className="mt-1 w-full" onClick={saveTemplate}>
                  <Save size={14} className="mr-2" />
                  Save as Template
                </Button>
              </div>
            )}
            {templates.length === 0 && (
              <Button variant="ghost" size="sm" className="w-full" onClick={saveTemplate}>
                <Save size={14} className="mr-2" />
                Save as Template
              </Button>
            )}
          </Card>
        </div>

        {/* Right: Report Preview (~60%) */}
        <div className="flex-1 min-w-0 flex flex-col gap-3">
          <Card padding="none" className="flex-1 flex flex-col min-h-0 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
              <h2 className="text-sm font-semibold text-[var(--color-text)]">Report Preview</h2>
              {reportRows.length > 0 && (
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={exportCsv}
                    disabled={exporting !== null}
                    title="Export as CSV (custom report data)"
                  >
                    <FileDown size={14} className="mr-1" />
                    CSV
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => exportViaApi('xlsx')}
                    disabled={exporting !== null}
                    isLoading={exporting === 'xlsx'}
                    title="Export trial balance as Excel"
                  >
                    <Download size={14} className="mr-1" />
                    Excel
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => exportViaApi('pdf')}
                    disabled={exporting !== null}
                    isLoading={exporting === 'pdf'}
                    title="Export trial balance as PDF"
                  >
                    <FileText size={14} className="mr-1" />
                    PDF
                  </Button>
                </div>
              )}
            </div>
            <div className="flex-1 overflow-auto p-0">
              {reportError && (
                <div className="flex items-center text-[var(--color-danger)] p-4">
                  <AlertCircle size={18} className="mr-2" /> {reportError}
                </div>
              )}
              {generating ? (
                <div className="flex items-center justify-center py-20 text-[var(--color-text-muted)]">
                  <Loader2 size={24} className="animate-spin mr-3" /> Generating report…
                </div>
              ) : reportRows.length === 0 && !reportError ? (
                <div className="flex flex-col items-center justify-center py-20 text-[var(--color-text-muted)]">
                  <FileSpreadsheet size={40} className="mb-3 opacity-40" />
                  <p className="text-lg font-medium">No Data</p>
                  <p className="text-sm mt-1">
                    Configure your report and click Generate Report to view results.
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-[var(--color-surface-hover)] z-[1]">
                      <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] text-xs uppercase tracking-wider">
                        <th className="py-3 px-4 text-left font-medium">Code</th>
                        <th className="py-3 px-3 text-left font-medium">Account</th>
                        <th className="py-3 px-3 text-left font-medium">Category</th>
                        {metrics.has('debit_total') && (
                          <th className="py-3 px-3 text-right font-medium w-32">Debit</th>
                        )}
                        {metrics.has('credit_total') && (
                          <th className="py-3 px-3 text-right font-medium w-32">Credit</th>
                        )}
                        {metrics.has('net_balance') && (
                          <th className="py-3 px-3 text-right font-medium w-32">Net</th>
                        )}
                        {metrics.has('transaction_count') && (
                          <th className="py-3 px-3 text-right font-medium w-24">Count</th>
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {displayedRows.map((row) => (
                        <tr
                          key={row.account_id}
                          className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors"
                        >
                          <td className="py-2.5 px-4 font-mono text-[var(--color-text-muted)]">
                            {row.account_code}
                          </td>
                          <td className="py-2.5 px-3 text-[var(--color-text)]">{row.account_name}</td>
                          <td className="py-2.5 px-3 text-[var(--color-text-muted)]">
                            {row.account_category || '—'}
                          </td>
                          {metrics.has('debit_total') && (
                            <td className="py-2.5 px-3 text-right font-mono tabular-nums">
                              {fmtNum(row.debit_total)}
                            </td>
                          )}
                          {metrics.has('credit_total') && (
                            <td className="py-2.5 px-3 text-right font-mono tabular-nums">
                              {fmtNum(row.credit_total)}
                            </td>
                          )}
                          {metrics.has('net_balance') && (
                            <td className="py-2.5 px-3 text-right font-mono tabular-nums">
                              {fmtNum(row.net_balance)}
                            </td>
                          )}
                          {metrics.has('transaction_count') && (
                            <td className="py-2.5 px-3 text-right font-mono tabular-nums">
                              {row.transaction_count ?? '—'}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                    {totals && reportRows.length > 0 && (
                      <tfoot>
                        <tr className="border-t-2 border-[var(--color-border)] bg-[var(--color-surface-hover)]/60 font-semibold">
                          <td className="py-3 px-4" />
                          <td className="py-3 px-3 text-right text-xs uppercase tracking-wider text-[var(--color-text-muted)]">
                            Total
                          </td>
                          <td className="py-3 px-3" />
                          {metrics.has('debit_total') && (
                            <td className="py-3 px-3 text-right font-mono tabular-nums">
                              {fmtNum(totals.debit_total)}
                            </td>
                          )}
                          {metrics.has('credit_total') && (
                            <td className="py-3 px-3 text-right font-mono tabular-nums">
                              {fmtNum(totals.credit_total)}
                            </td>
                          )}
                          {metrics.has('net_balance') && (
                            <td className="py-3 px-3 text-right font-mono tabular-nums">
                              {fmtNum(totals.net_balance)}
                            </td>
                          )}
                          {metrics.has('transaction_count') && <td className="py-3 px-3" />}
                        </tr>
                      </tfoot>
                    )}
                  </table>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
