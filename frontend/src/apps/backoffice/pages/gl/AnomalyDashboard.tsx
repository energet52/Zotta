import { useEffect, useState, useCallback, Fragment } from 'react';
import { Link } from 'react-router-dom';
import {
  ShieldAlert,
  Loader2,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  XCircle,
  Download,
  Filter,
} from 'lucide-react';
import Card from '../../../../components/ui/Card';
import Button from '../../../../components/ui/Button';
import { glApi, type GLAnomaly } from '../../../../api/glApi';

/* ── types ───────────────────────────────────── */

const STATUS_OPTIONS = ['open', 'reviewed', 'dismissed'] as const;

/* ── helpers ─────────────────────────────────── */

const fmtDate = (d: string | null) =>
  d ? new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';

function getRiskColor(score: number): string {
  if (score < 25) return 'var(--color-success)';
  if (score < 50) return 'var(--color-warning)';
  if (score < 75) return '#f97316'; // orange
  return 'var(--color-danger)';
}

/* ── Risk bar ─────────────────────────────────── */

function RiskBar({ score }: { score: number }) {
  const color = getRiskColor(score);
  const pct = Math.min(100, score);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full bg-[var(--color-surface-hover)] overflow-hidden min-w-[60px] max-w-[100px]">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs font-medium" style={{ color }}>
        {score}
      </span>
    </div>
  );
}

/* ── main page ───────────────────────────────── */

export default function AnomalyDashboard() {
  const [anomalies, setAnomalies] = useState<GLAnomaly[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('open');
  const [minRiskScore, setMinRiskScore] = useState<number>(0);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [actingId, setActingId] = useState<number | null>(null);

  const fetchAnomalies = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const params: { status?: string; min_risk_score?: number } = {};
      if (statusFilter && statusFilter !== 'all') params.status = statusFilter;
      if (minRiskScore > 0) params.min_risk_score = minRiskScore;
      const { data } = await glApi.getAnomalies({ ...params, limit: 500 });
      setAnomalies(Array.isArray(data) ? data : []);
    } catch {
      setError('Failed to load anomalies');
      setAnomalies([]);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, minRiskScore]);

  useEffect(() => {
    fetchAnomalies();
  }, [fetchAnomalies]);

  const handleReview = async (id: number, action: 'reviewed' | 'dismissed') => {
    setActingId(id);
    try {
      await glApi.reviewAnomaly(id, action);
      setAnomalies((prev) =>
        prev.map((a) =>
          a.id === id
            ? {
                ...a,
                status: action,
                reviewed_at: new Date().toISOString(),
              }
            : a
        )
      );
      setExpandedId((prev) => (prev === id ? null : prev));
    } finally {
      setActingId(null);
    }
  };

  const openCount = anomalies.filter((a) => a.status === 'open').length;
  const highRiskCount = anomalies.filter((a) => a.risk_score > 75).length;
  const mediumRiskCount = anomalies.filter((a) => a.risk_score >= 25 && a.risk_score <= 75).length;
  const lowRiskCount = anomalies.filter((a) => a.risk_score < 25).length;

  const filtered = anomalies;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-[var(--color-primary)]/10">
            <ShieldAlert size={22} className="text-[var(--color-primary)]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-text)]">Anomaly Dashboard</h1>
            <p className="text-sm text-[var(--color-text-muted)]">AI-flagged journal entry anomalies</p>
          </div>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card padding="sm" className="hover:bg-[var(--color-surface-hover)] transition-colors">
          <p className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">Total Open</p>
          <p className="mt-1 text-2xl font-bold text-[var(--color-text)]">{openCount}</p>
        </Card>
        <Card padding="sm" className="hover:bg-[var(--color-surface-hover)] transition-colors">
          <p className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">High Risk (&gt;75)</p>
          <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--color-danger)' }}>
            {highRiskCount}
          </p>
        </Card>
        <Card padding="sm" className="hover:bg-[var(--color-surface-hover)] transition-colors">
          <p className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">Medium Risk (25-75)</p>
          <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--color-warning)' }}>
            {mediumRiskCount}
          </p>
        </Card>
        <Card padding="sm" className="hover:bg-[var(--color-surface-hover)] transition-colors">
          <p className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">Low Risk (&lt;25)</p>
          <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--color-success)' }}>
            {lowRiskCount}
          </p>
        </Card>
      </div>

      {/* Filters */}
      <Card padding="md">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2 text-sm text-[var(--color-text-muted)]">
            <Filter size={16} />
            <span>Filters</span>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-[var(--color-text-muted)]">Status</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            >
              <option value="all">All</option>
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-[var(--color-text-muted)]">Min risk score</label>
            <input
              type="number"
              min={0}
              max={100}
              value={minRiskScore || ''}
              onChange={(e) => setMinRiskScore(e.target.value ? parseInt(e.target.value, 10) : 0)}
              className="w-20 px-3 py-2 text-sm rounded-lg border bg-[var(--color-surface)] text-[var(--color-text)] border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            />
          </div>
        </div>
      </Card>

      {/* Table */}
      <Card padding="none">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
          <h2 className="text-sm font-semibold text-[var(--color-text)]">Flagged Entries</h2>
          <Button variant="secondary" size="sm" disabled>
            <Download size={16} className="mr-1.5" />
            Export
          </Button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20 text-[var(--color-text-muted)]">
            <Loader2 size={24} className="animate-spin mr-3" /> Loading anomalies…
          </div>
        ) : error ? (
          <div className="flex items-center justify-center py-20 text-[var(--color-danger)]">
            {error}
          </div>
        ) : filtered.length === 0 ? (
          <div className="py-16 text-center text-[var(--color-text-muted)] text-sm">
            No anomalies match your filters.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] text-xs uppercase tracking-wider">
                  <th className="w-8 py-3 px-2"></th>
                  <th className="py-3 px-4 text-left font-medium">Created</th>
                  <th className="py-3 px-3 text-left font-medium">Entry ID</th>
                  <th className="py-3 px-3 text-left font-medium">Type</th>
                  <th className="py-3 px-3 text-left font-medium">Risk Score</th>
                  <th className="py-3 px-3 text-left font-medium">Explanation</th>
                  <th className="py-3 px-3 text-left font-medium">Status</th>
                  <th className="py-3 px-4 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((a) => (
                  <Fragment key={a.id}>
                    <tr
                      key={a.id}
                      className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors cursor-pointer"
                      onClick={() => setExpandedId((prev) => (prev === a.id ? null : a.id))}
                    >
                      <td className="py-2.5 px-2">
                        {expandedId === a.id ? (
                          <ChevronDown size={16} className="text-[var(--color-text-muted)]" />
                        ) : (
                          <ChevronRight size={16} className="text-[var(--color-text-muted)]" />
                        )}
                      </td>
                      <td className="py-2.5 px-4 text-[var(--color-text-muted)]">
                        {fmtDate(a.created_at)}
                      </td>
                      <td className="py-2.5 px-3">
                        <Link
                          to={`/backoffice/gl/entries?entry=${a.journal_entry_id}`}
                          className="font-mono text-xs text-[var(--color-primary)] hover:underline"
                          onClick={(e) => e.stopPropagation()}
                        >
                          #{a.journal_entry_id}
                        </Link>
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--color-surface-hover)] text-[var(--color-text)]">
                          {a.anomaly_type}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <RiskBar score={a.risk_score} />
                      </td>
                      <td className="py-2.5 px-3 text-[var(--color-text)] max-w-[220px] truncate">
                        {a.explanation || '—'}
                      </td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full capitalize ${
                            a.status === 'open'
                              ? 'bg-amber-500/20 text-amber-400'
                              : a.status === 'reviewed'
                                ? 'bg-emerald-500/20 text-emerald-400'
                                : 'bg-gray-500/20 text-gray-400'
                          }`}
                        >
                          {a.status}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-right" onClick={(e) => e.stopPropagation()}>
                        {a.status === 'open' && (
                          <div className="flex items-center justify-end gap-1">
                            <button
                              onClick={() => handleReview(a.id, 'reviewed')}
                              disabled={actingId !== null}
                              className="p-1.5 rounded-lg hover:bg-[var(--color-success)]/20 text-[var(--color-success)] disabled:opacity-50"
                              title="Mark as Reviewed"
                            >
                              {actingId === a.id ? (
                                <Loader2 size={16} className="animate-spin" />
                              ) : (
                                <CheckCircle2 size={16} />
                              )}
                            </button>
                            <button
                              onClick={() => handleReview(a.id, 'dismissed')}
                              disabled={actingId !== null}
                              className="p-1.5 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] disabled:opacity-50"
                              title="Dismiss"
                            >
                              <XCircle size={16} />
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                    {expandedId === a.id && (
                      <tr key={`${a.id}-exp`} className="border-b border-[var(--color-border)] bg-[var(--color-surface-hover)]/50">
                        <td colSpan={8} className="py-3 px-4">
                          <div className="text-sm text-[var(--color-text-muted)]">
                            <p className="font-medium text-[var(--color-text)] mb-1">Full explanation</p>
                            <p className="whitespace-pre-wrap">{a.explanation || 'No explanation.'}</p>
                            {a.reviewed_at && (
                              <p className="mt-2 text-xs">
                                Reviewed {fmtDate(a.reviewed_at)}
                              </p>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
