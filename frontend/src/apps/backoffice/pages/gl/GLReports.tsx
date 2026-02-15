import { useEffect, useState, useCallback, useRef } from 'react';
import {
  FileBarChart,
  FileSpreadsheet,
  Download,
  BarChart2,
  Loader2,
  AlertCircle,
  ChevronDown,
  ArrowLeft,
} from 'lucide-react';
import api from '../../../../api/client';
import Card from '../../../../components/ui/Card';
import Button from '../../../../components/ui/Button';
import { glApi, type AccountingPeriod, type GLAccount } from '../../../../api/glApi';

/* ── Types ───────────────────────────────────────────────────────── */

interface ReportType {
  key: string;
  name: string;
  description: string;
}

interface ReportResponse {
  report_type: string;
  report_name: string;
  data: Record<string, unknown> | Record<string, unknown>[];
}

const EXPORT_FORMATS = [
  { value: 'csv', label: 'CSV' },
  { value: 'xlsx', label: 'Excel' },
  { value: 'pdf', label: 'PDF' },
  { value: 'json', label: 'JSON' },
] as const;

/* ── Helpers ─────────────────────────────────────────────────────── */

const fmtNum = (n: unknown): string => {
  if (n === null || n === undefined) return '—';
  const num = Number(n);
  if (Number.isNaN(num)) return String(n);
  return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const isNumericCol = (key: string, sample: unknown): boolean => {
  const val = sample && typeof sample === 'object' && key in sample ? (sample as Record<string, unknown>)[key] : null;
  return typeof val === 'number' || (typeof val === 'string' && /^-?[\d.]+$/.test(val));
};

/* ── GL Reports Page ─────────────────────────────────────────────── */

export default function GLReports() {
  const [reportTypes, setReportTypes] = useState<ReportType[]>([]);
  const [periods, setPeriods] = useState<AccountingPeriod[]>([]);
  const [accounts, setAccounts] = useState<GLAccount[]>([]);
  const [loadingTypes, setLoadingTypes] = useState(true);
  const [loadingReport, setLoadingReport] = useState(false);
  const [loadingExport, setLoadingExport] = useState(false);
  const [error, setError] = useState('');
  const [reportError, setReportError] = useState('');

  const [selectedType, setSelectedType] = useState<ReportType | null>(null);
  const [periodId, setPeriodId] = useState<string>('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [accountId, setAccountId] = useState<string>('');
  const [reportData, setReportData] = useState<ReportResponse | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const exportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (exportRef.current && !exportRef.current.contains(e.target as Node)) {
        setExportOpen(false);
      }
    };
    if (exportOpen) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [exportOpen]);

  /* Load report types */
  useEffect(() => {
    api
      .get<ReportType[]>('/gl/reports/types')
      .then(({ data }) => setReportTypes(data))
      .catch(() => setError('Failed to load report types'))
      .finally(() => setLoadingTypes(false));
  }, []);

  /* Load periods and accounts */
  useEffect(() => {
    glApi.getPeriods().then(({ data }) => setPeriods(data)).catch(() => {});
    glApi.getAccounts().then(({ data }) => setAccounts(data)).catch(() => {});
  }, []);

  /* Generate report */
  const generateReport = useCallback(async () => {
    if (!selectedType) return;
    try {
      setLoadingReport(true);
      setReportError('');
      setReportData(null);
      const params: Record<string, string | number | undefined> = {};
      if (periodId) params.period_id = periodId;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      if (accountId && selectedType.key === 'account_activity') params.account_id = accountId;

      const { data } = await api.get<ReportResponse>(`/gl/reports/${selectedType.key}`, { params });
      setReportData(data);
    } catch {
      setReportError('Failed to generate report');
    } finally {
      setLoadingReport(false);
    }
  }, [selectedType, periodId, dateFrom, dateTo, accountId]);

  /* Export */
  const handleExport = async (format: string) => {
    if (!selectedType) return;
    setExportOpen(false);
    setLoadingExport(true);
    try {
      const params: Record<string, string | number> = {};
      if (periodId) params.period_id = Number(periodId);

      const { data } = await api.post(
        `/gl/reports/${selectedType.key}/export`,
        {
          format,
          export_type: `report_${selectedType.key}`,
          filters: { period_id: periodId || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined, account_id: accountId || undefined },
          title: selectedType.name,
        },
        { responseType: 'blob', params }
      );

      const blob = data as Blob;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = format === 'xlsx' ? 'xlsx' : format === 'pdf' ? 'pdf' : format;
      a.download = `gl_report_${selectedType.key}.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setReportError('Failed to export report');
    } finally {
      setLoadingExport(false);
    }
  };

  /* Normalize report data to rows for table */
  const getRowsAndColumns = (): { rows: Record<string, unknown>[]; columns: string[] } => {
    if (!reportData?.data) return { rows: [], columns: [] };
    const d = reportData.data;
    let rows: Record<string, unknown>[] = [];
    if (Array.isArray(d)) {
      rows = d as Record<string, unknown>[];
    } else if (typeof d === 'object') {
      const obj = d as Record<string, unknown>;
      if (obj.items && Array.isArray(obj.items)) {
        rows = obj.items as Record<string, unknown>[];
      } else if (obj.sections && typeof obj.sections === 'object') {
        const sections = obj.sections as Record<string, { items?: unknown[]; total?: unknown }>;
        const flat: Record<string, unknown>[] = [];
        for (const [secName, sec] of Object.entries(sections)) {
          const items = (sec as { items?: unknown[] }).items;
          if (Array.isArray(items)) {
            for (const item of items as Record<string, unknown>[]) {
              flat.push({ ...item, _section: secName });
            }
          }
          if (sec.total !== undefined) {
            flat.push({ _section: secName, _total: sec.total });
          }
        }
        rows = flat;
      } else {
        rows = [obj];
      }
    }
    if (rows.length === 0) return { rows: [], columns: [] };
    const allKeys = new Set<string>();
    for (const r of rows) {
      for (const k of Object.keys(r)) {
        if (!k.startsWith('_')) allKeys.add(k);
      }
    }
    const columns = Array.from(allKeys).sort();
    return { rows, columns };
  };

  const { rows, columns } = getRowsAndColumns();

  /* Infer numeric columns from first row */
  const numericCols = new Set<string>();
  if (rows[0]) {
    for (const col of columns) {
      if (isNumericCol(col, rows[0])) numericCols.add(col);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-[var(--color-primary)]/10">
            <FileBarChart size={22} className="text-[var(--color-primary)]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-text)]">GL Reports</h1>
            <p className="text-sm text-[var(--color-text-muted)]">
              Generate and export standard financial reports
            </p>
          </div>
        </div>
      </div>

      {loadingTypes ? (
        <Card>
          <div className="flex items-center justify-center py-20 text-[var(--color-text-muted)]">
            <Loader2 size={24} className="animate-spin mr-3" /> Loading report catalog…
          </div>
        </Card>
      ) : error ? (
        <Card>
          <div className="flex items-center justify-center py-20 text-[var(--color-danger)]">
            <AlertCircle size={20} className="mr-2" /> {error}
          </div>
        </Card>
      ) : !selectedType ? (
        /* Report catalog */
        <div>
          <h2 className="text-lg font-semibold text-[var(--color-text)] mb-4">Report Catalog</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {reportTypes.map((rt) => (
              <Card key={rt.key} padding="md" className="flex flex-col">
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-lg bg-[var(--color-surface-hover)]">
                    <BarChart2 size={20} className="text-[var(--color-primary)]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-[var(--color-text)]">{rt.name}</h3>
                    <p className="text-sm text-[var(--color-text-muted)] mt-1 line-clamp-2">
                      {rt.description}
                    </p>
                  </div>
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  className="mt-4 w-full"
                  onClick={() => setSelectedType(rt)}
                  disabled={loadingReport}
                >
                  <FileSpreadsheet size={14} className="mr-2" />
                  Generate
                </Button>
              </Card>
            ))}
          </div>
        </div>
      ) : (
        /* Report parameters and results */
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                setSelectedType(null);
                setReportData(null);
                setReportError('');
              }}
              className="p-2 rounded-lg text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text)] transition-colors"
            >
              <ArrowLeft size={20} />
            </button>
            <h2 className="text-lg font-semibold text-[var(--color-text)]">{selectedType.name}</h2>
          </div>

          {/* Parameters */}
          <Card padding="sm">
            <div className="flex flex-wrap items-end gap-4">
              <div className="min-w-[180px]">
                <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">
                  Period
                </label>
                <select
                  value={periodId}
                  onChange={(e) => setPeriodId(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                >
                  <option value="">Any</option>
                  {periods.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="min-w-[140px]">
                <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">
                  Date From
                </label>
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                />
              </div>
              <div className="min-w-[140px]">
                <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">
                  Date To
                </label>
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                />
              </div>
              {selectedType.key === 'account_activity' && (
                <div className="min-w-[220px]">
                  <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">
                    Account
                  </label>
                  <select
                    value={accountId}
                    onChange={(e) => setAccountId(e.target.value)}
                    className="w-full px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                  >
                    <option value="">All accounts</option>
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.account_code} – {a.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <Button
                variant="primary"
                size="sm"
                onClick={generateReport}
                isLoading={loadingReport}
                disabled={loadingReport}
              >
                {loadingReport ? (
                  <Loader2 size={16} className="animate-spin mr-2" />
                ) : (
                  <BarChart2 size={16} className="mr-2" />
                )}
                Generate
              </Button>
              {reportData && (
                <div className="relative ml-auto" ref={exportRef}>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setExportOpen(!exportOpen)}
                    disabled={loadingExport}
                  >
                    <Download size={16} className="mr-2" />
                    Export
                    <ChevronDown size={14} className="ml-1" />
                  </Button>
                  {exportOpen && (
                    <div className="absolute right-0 mt-1 py-1 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-lg z-10 min-w-[120px]">
                      {EXPORT_FORMATS.map(({ value, label }) => (
                        <button
                          key={value}
                          onClick={() => handleExport(value)}
                          className="block w-full text-left px-4 py-2 text-sm text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </Card>

          {reportError && (
            <div className="flex items-center text-[var(--color-danger)]">
              <AlertCircle size={18} className="mr-2" /> {reportError}
            </div>
          )}

          {/* Results table */}
          {loadingReport ? (
            <Card>
              <div className="flex items-center justify-center py-20 text-[var(--color-text-muted)]">
                <Loader2 size={24} className="animate-spin mr-3" /> Generating report…
              </div>
            </Card>
          ) : reportData && rows.length > 0 ? (
            <Card padding="none">
              <div className="max-h-[500px] overflow-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-[var(--color-surface-hover)] z-[1]">
                    <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] text-xs uppercase tracking-wider">
                      {columns.map((col) => (
                        <th
                          key={col}
                          className={`py-3 px-4 font-medium ${
                            numericCols.has(col) ? 'text-right' : 'text-left'
                          }`}
                        >
                          {col.replace(/_/g, ' ')}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, idx) => (
                      <tr
                        key={idx}
                        className={`border-b border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors ${
                          '_total' in row ? 'font-semibold bg-[var(--color-surface-hover)]/50' : ''
                        }`}
                      >
                        {columns.map((col) => (
                          <td
                            key={col}
                            className={`py-2.5 px-4 ${
                              numericCols.has(col)
                                ? 'text-right font-mono tabular-nums'
                                : 'text-left'
                            }`}
                          >
                            {numericCols.has(col)
                              ? fmtNum((row as Record<string, unknown>)[col])
                              : String((row as Record<string, unknown>)[col] ?? '—')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          ) : reportData && rows.length === 0 ? (
            <Card>
              <div className="flex flex-col items-center justify-center py-20 text-[var(--color-text-muted)]">
                <FileBarChart size={40} className="mb-3 opacity-40" />
                <p className="text-lg font-medium">No Data</p>
                <p className="text-sm mt-1">
                  No data returned for this report with the selected parameters.
                </p>
              </div>
            </Card>
          ) : null}
        </div>
      )}
    </div>
  );
}
