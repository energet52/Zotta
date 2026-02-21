import { useEffect, useState, useCallback } from 'react';
import {
  AlertTriangle, Bug, CheckCircle, Clock, ChevronDown,
  ChevronUp, Search, RefreshCw, XCircle, Filter,
  Shield, AlertOctagon, Info,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import Badge from '../../../components/ui/Badge';
import { errorLogApi } from '../../../api/endpoints';

interface ErrorLogEntry {
  id: number;
  severity: string;
  error_type: string;
  message: string;
  traceback: string | null;
  module: string | null;
  function_name: string | null;
  line_number: number | null;
  request_method: string | null;
  request_path: string | null;
  request_body: string | null;
  status_code: number | null;
  response_time_ms: number | null;
  user_id: number | null;
  user_email: string | null;
  ip_address: string | null;
  resolved: boolean;
  resolved_by: number | null;
  resolved_at: string | null;
  resolution_notes: string | null;
  created_at: string;
}

interface ErrorStats {
  period_hours: number;
  total_in_period: number;
  unresolved: number;
  by_severity: Record<string, number>;
  top_error_types: { error_type: string; count: number }[];
  top_paths: { path: string; count: number }[];
  hourly: { hour: string; count: number }[];
}

const SEVERITY_CONFIG: Record<string, { icon: typeof Bug; color: string; bg: string; label: string }> = {
  critical: { icon: AlertOctagon, color: 'text-red-400', bg: 'bg-red-500/10', label: 'Critical' },
  error: { icon: XCircle, color: 'text-orange-400', bg: 'bg-orange-500/10', label: 'Error' },
  warning: { icon: AlertTriangle, color: 'text-yellow-400', bg: 'bg-yellow-500/10', label: 'Warning' },
  info: { icon: Info, color: 'text-blue-400', bg: 'bg-blue-500/10', label: 'Info' },
};

function timeAgo(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export default function ErrorMonitor() {
  const [stats, setStats] = useState<ErrorStats | null>(null);
  const [logs, setLogs] = useState<ErrorLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Filters
  const [severity, setSeverity] = useState('');
  const [resolved, setResolved] = useState<string>('false');
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [page, setPage] = useState(0);
  const [statsPeriod, setStatsPeriod] = useState(24);
  const limit = 30;

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { limit, offset: page * limit };
      if (severity) params.severity = severity;
      if (resolved !== '') params.resolved = resolved === 'true';
      if (search) params.search = search;

      const [logsRes, statsRes] = await Promise.all([
        errorLogApi.list(params),
        errorLogApi.stats(statsPeriod),
      ]);
      setLogs(logsRes.data.items);
      setTotal(logsRes.data.total);
      setStats(statsRes.data);
    } catch (err) {
      console.error('Failed to load error logs', err);
    } finally {
      setLoading(false);
    }
  }, [severity, resolved, search, page, statsPeriod]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleResolve = async (id: number) => {
    try {
      await errorLogApi.resolve(id);
      loadData();
    } catch (err) {
      console.error('Failed to resolve', err);
    }
  };

  const handleUnresolve = async (id: number) => {
    try {
      await errorLogApi.unresolve(id);
      loadData();
    } catch (err) {
      console.error('Failed to unresolve', err);
    }
  };

  const handleBulkResolve = async () => {
    if (selectedIds.size === 0) return;
    try {
      await errorLogApi.bulkResolve(Array.from(selectedIds));
      setSelectedIds(new Set());
      loadData();
    } catch (err) {
      console.error('Bulk resolve failed', err);
    }
  };

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === logs.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(logs.map(l => l.id)));
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(0);
  };

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Bug size={24} /> Error Monitor
          </h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            Real-time application error tracking and resolution
          </p>
        </div>
        <Button onClick={loadData} variant="secondary" className="flex items-center gap-2">
          <RefreshCw size={14} /> Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-[var(--color-text-muted)]">Errors ({statsPeriod}h)</p>
                <p className="text-2xl font-bold mt-1">{stats.total_in_period}</p>
              </div>
              <div className="p-2 rounded-lg bg-red-500/10">
                <Bug size={20} className="text-red-400" />
              </div>
            </div>
          </Card>
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-[var(--color-text-muted)]">Unresolved</p>
                <p className="text-2xl font-bold mt-1">{stats.unresolved}</p>
              </div>
              <div className="p-2 rounded-lg bg-orange-500/10">
                <AlertTriangle size={20} className="text-orange-400" />
              </div>
            </div>
          </Card>
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-[var(--color-text-muted)]">Critical</p>
                <p className="text-2xl font-bold mt-1">{stats.by_severity.critical || 0}</p>
              </div>
              <div className="p-2 rounded-lg bg-red-500/10">
                <AlertOctagon size={20} className="text-red-400" />
              </div>
            </div>
          </Card>
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-[var(--color-text-muted)]">Period</p>
                <select
                  value={statsPeriod}
                  onChange={(e) => setStatsPeriod(Number(e.target.value))}
                  className="text-sm bg-transparent border-none text-[var(--color-text)] font-bold mt-1 cursor-pointer"
                >
                  <option value={1}>1 hour</option>
                  <option value={6}>6 hours</option>
                  <option value={24}>24 hours</option>
                  <option value={72}>3 days</option>
                  <option value={168}>7 days</option>
                  <option value={720}>30 days</option>
                </select>
              </div>
              <div className="p-2 rounded-lg bg-blue-500/10">
                <Clock size={20} className="text-blue-400" />
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Top Errors */}
      {stats && (stats.top_error_types.length > 0 || stats.top_paths.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {stats.top_error_types.length > 0 && (
            <Card className="p-4">
              <h3 className="text-sm font-semibold mb-3">Top Error Types</h3>
              <div className="space-y-2">
                {stats.top_error_types.map((t, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span className="text-[var(--color-text-muted)] truncate mr-2 font-mono text-xs">{t.error_type}</span>
                    <Badge variant="danger">{t.count}</Badge>
                  </div>
                ))}
              </div>
            </Card>
          )}
          {stats.top_paths.length > 0 && (
            <Card className="p-4">
              <h3 className="text-sm font-semibold mb-3">Top Failing Endpoints</h3>
              <div className="space-y-2">
                {stats.top_paths.map((t, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span className="text-[var(--color-text-muted)] truncate mr-2 font-mono text-xs">{t.path}</span>
                    <Badge variant="danger">{t.count}</Badge>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Filters */}
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <Filter size={14} className="text-[var(--color-text-muted)]" />

          <select
            value={severity}
            onChange={(e) => { setSeverity(e.target.value); setPage(0); }}
            className="h-[34px] px-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)]"
          >
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="error">Error</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>

          <select
            value={resolved}
            onChange={(e) => { setResolved(e.target.value); setPage(0); }}
            className="h-[34px] px-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)]"
          >
            <option value="">All Status</option>
            <option value="false">Unresolved</option>
            <option value="true">Resolved</option>
          </select>

          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 flex-1 min-w-[200px]">
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
              <input
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search errors..."
                className="w-full h-[34px] pl-8 pr-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)]"
              />
            </div>
            <Button type="submit" variant="secondary" className="h-[34px] text-xs px-3">Search</Button>
          </form>

          {selectedIds.size > 0 && (
            <Button onClick={handleBulkResolve} variant="primary" className="h-[34px] text-xs px-3 flex items-center gap-1">
              <CheckCircle size={12} /> Resolve {selectedIds.size}
            </Button>
          )}
        </div>
      </Card>

      {/* Error List */}
      <Card className="overflow-hidden">
        {/* Table Header */}
        <div className="grid grid-cols-[32px_80px_1fr_150px_120px_100px_80px] gap-2 px-4 py-2.5 bg-[var(--color-surface-hover)] border-b border-[var(--color-border)] text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">
          <div>
            <input type="checkbox" checked={logs.length > 0 && selectedIds.size === logs.length} onChange={toggleSelectAll} className="rounded" />
          </div>
          <div>Severity</div>
          <div>Error</div>
          <div>Endpoint</div>
          <div>Module</div>
          <div>When</div>
          <div>Status</div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-32 text-[var(--color-text-muted)]">Loading...</div>
        ) : logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-[var(--color-text-muted)]">
            <Shield size={32} className="mb-2 opacity-50" />
            <p className="text-sm">No errors found</p>
          </div>
        ) : (
          logs.map((log) => {
            const sev = SEVERITY_CONFIG[log.severity] || SEVERITY_CONFIG.error;
            const SevIcon = sev.icon;
            const isExpanded = expandedId === log.id;

            return (
              <div key={log.id} className="border-b border-[var(--color-border)] last:border-b-0">
                {/* Row */}
                <div
                  className="grid grid-cols-[32px_80px_1fr_150px_120px_100px_80px] gap-2 px-4 py-3 items-center hover:bg-[var(--color-surface-hover)] cursor-pointer transition-colors"
                  onClick={() => setExpandedId(isExpanded ? null : log.id)}
                >
                  <div onClick={(e) => e.stopPropagation()}>
                    <input type="checkbox" checked={selectedIds.has(log.id)} onChange={() => toggleSelect(log.id)} className="rounded" />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <SevIcon size={14} className={sev.color} />
                    <span className={`text-xs font-medium ${sev.color}`}>{sev.label}</span>
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{log.error_type}</p>
                    <p className="text-xs text-[var(--color-text-muted)] truncate">{log.message}</p>
                  </div>
                  <div className="text-xs font-mono text-[var(--color-text-muted)] truncate">
                    {log.request_method && log.request_path
                      ? `${log.request_method} ${log.request_path}`
                      : '-'
                    }
                  </div>
                  <div className="text-xs text-[var(--color-text-muted)] truncate">
                    {log.module ? log.module.split('/').pop()?.replace('.py', '') : '-'}
                  </div>
                  <div className="text-xs text-[var(--color-text-muted)]">
                    {timeAgo(log.created_at)}
                  </div>
                  <div className="flex items-center gap-1">
                    {log.resolved ? (
                      <span className="text-xs text-green-400 flex items-center gap-1"><CheckCircle size={12} /> Fixed</span>
                    ) : (
                      <span className="text-xs text-orange-400 flex items-center gap-1"><Clock size={12} /> Open</span>
                    )}
                    {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </div>
                </div>

                {/* Expanded Detail */}
                {isExpanded && (
                  <div className="px-4 pb-4 pt-1 bg-[var(--color-bg)] border-t border-[var(--color-border)]">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                      <div>
                        <p className="text-xs text-[var(--color-text-muted)] mb-1">Module</p>
                        <p className="text-sm font-mono">{log.module || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-[var(--color-text-muted)] mb-1">Function</p>
                        <p className="text-sm font-mono">{log.function_name || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-[var(--color-text-muted)] mb-1">Line</p>
                        <p className="text-sm font-mono">{log.line_number || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-[var(--color-text-muted)] mb-1">Status Code</p>
                        <p className="text-sm font-mono">{log.status_code || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-[var(--color-text-muted)] mb-1">Response Time</p>
                        <p className="text-sm">{log.response_time_ms ? `${log.response_time_ms}ms` : '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-[var(--color-text-muted)] mb-1">IP Address</p>
                        <p className="text-sm font-mono">{log.ip_address || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-[var(--color-text-muted)] mb-1">User ID</p>
                        <p className="text-sm">{log.user_id || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-[var(--color-text-muted)] mb-1">Timestamp</p>
                        <p className="text-sm">{new Date(log.created_at).toLocaleString()}</p>
                      </div>
                    </div>

                    {log.request_body && (
                      <div className="mb-4">
                        <p className="text-xs text-[var(--color-text-muted)] mb-1">Request Body</p>
                        <pre className="text-xs p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] overflow-x-auto max-h-32 font-mono">
                          {(() => {
                            try { return JSON.stringify(JSON.parse(log.request_body), null, 2); }
                            catch { return log.request_body; }
                          })()}
                        </pre>
                      </div>
                    )}

                    {log.traceback && (
                      <div className="mb-4">
                        <p className="text-xs text-[var(--color-text-muted)] mb-1">Traceback</p>
                        <pre className="text-xs p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] overflow-x-auto max-h-64 font-mono text-red-400/80 whitespace-pre-wrap">
                          {log.traceback}
                        </pre>
                      </div>
                    )}

                    {log.resolution_notes && (
                      <div className="mb-4">
                        <p className="text-xs text-[var(--color-text-muted)] mb-1">Resolution Notes</p>
                        <p className="text-sm bg-[var(--color-surface)] p-2 rounded-lg border border-[var(--color-border)]">{log.resolution_notes}</p>
                      </div>
                    )}

                    <div className="flex gap-2">
                      {log.resolved ? (
                        <Button onClick={() => handleUnresolve(log.id)} variant="secondary" className="text-xs flex items-center gap-1">
                          <XCircle size={12} /> Mark Unresolved
                        </Button>
                      ) : (
                        <Button onClick={() => handleResolve(log.id)} variant="primary" className="text-xs flex items-center gap-1">
                          <CheckCircle size={12} /> Mark Resolved
                        </Button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--color-border)]">
            <p className="text-xs text-[var(--color-text-muted)]">
              {page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total}
            </p>
            <div className="flex gap-2">
              <Button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} variant="secondary" className="text-xs h-[30px] px-3">
                Prev
              </Button>
              <Button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1} variant="secondary" className="text-xs h-[30px] px-3">
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
