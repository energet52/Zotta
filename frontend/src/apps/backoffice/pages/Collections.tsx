import { useEffect, useState, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  AlertTriangle, Search, Download, Users, ChevronLeft, ChevronRight,
  ArrowUpDown, Shield, ShieldAlert, Phone, MessageSquare, Gavel,
  Send, Scale, UserCheck, AlertCircle, RefreshCw,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Badge from '../../../components/ui/Badge';
import Button from '../../../components/ui/Button';
import { collectionsApi, underwriterApi } from '../../../api/endpoints';

interface CollectionEntry {
  id: number;
  reference_number: string;
  applicant_id: number;
  applicant_name: string;
  amount_approved: number | null;
  amount_due: number;
  days_past_due: number;
  last_contact: string | null;
  next_action: string | null;
  total_paid: number;
  outstanding_balance: number;
  phone: string | null;
  case_id: number | null;
  case_status: string | null;
  delinquency_stage: string | null;
  assigned_agent_id: number | null;
  assigned_agent_name: string | null;
  next_best_action: string | null;
  nba_confidence: number | null;
  dispute_active: boolean;
  vulnerability_flag: boolean;
  do_not_contact: boolean;
  hardship_flag: boolean;
  priority_score: number;
}

const STAGE_OPTIONS = [
  { value: '', label: 'All Stages' },
  { value: 'early_1_30', label: 'Early (1-30)' },
  { value: 'mid_31_60', label: 'Mid (31-60)' },
  { value: 'late_61_90', label: 'Late (61-90)' },
  { value: 'severe_90_plus', label: 'Severe (90+)' },
];

const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'settled', label: 'Settled' },
  { value: 'legal', label: 'Legal' },
];

const NBA_ICONS: Record<string, { icon: typeof Phone; color: string; label: string }> = {
  send_whatsapp_reminder: { icon: MessageSquare, color: 'text-emerald-400', label: 'WhatsApp' },
  send_sms_reminder: { icon: Send, color: 'text-blue-400', label: 'SMS' },
  call_now: { icon: Phone, color: 'text-amber-400', label: 'Call Now' },
  escalate_supervisor: { icon: UserCheck, color: 'text-orange-400', label: 'Escalate Sup.' },
  escalate_field: { icon: Users, color: 'text-red-400', label: 'Field Visit' },
  send_demand_letter: { icon: Gavel, color: 'text-red-400', label: 'Demand Letter' },
  escalate_legal: { icon: Scale, color: 'text-red-500', label: 'Legal' },
  hold_dispute: { icon: ShieldAlert, color: 'text-purple-400', label: 'Dispute Hold' },
  hold_do_not_contact: { icon: Shield, color: 'text-gray-400', label: 'DNC' },
  hold_vulnerability_review: { icon: AlertCircle, color: 'text-purple-400', label: 'Vulnerability' },
  offer_hardship_plan: { icon: Users, color: 'text-blue-400', label: 'Hardship Plan' },
};

const PAGE_SIZE = 25;

export default function Collections() {
  const [queue, setQueue] = useState<CollectionEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [stage, setStage] = useState('');
  const [status, setStatus] = useState('');
  const [sortBy, setSortBy] = useState('days_past_due');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(0);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [agents, setAgents] = useState<Array<{ id: number; name: string }>>([]);
  const [assignAgent, setAssignAgent] = useState<number | null>(null);
  const [showBulkAssign, setShowBulkAssign] = useState(false);
  const navigate = useNavigate();

  useEffect(() => { loadQueue(); loadAgents(); }, []);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = {};
      if (search) params.search = search;
      if (stage) params.stage = stage;
      if (status) params.status = status;
      params.sort_by = sortBy;
      params.sort_dir = sortDir;
      params.limit = 1000;
      const res = await collectionsApi.getQueue(params);
      setQueue(res.data);
    } catch { /* ignore */ }
    setLoading(false);
  }, [search, stage, status, sortBy, sortDir]);

  useEffect(() => { loadQueue(); }, [search, stage, status, sortBy, sortDir]);

  const loadAgents = async () => {
    try {
      const res = await underwriterApi.getStaff();
      setAgents(res.data.map((u: any) => ({ id: u.id, name: `${u.first_name} ${u.last_name}` })));
    } catch { /* ignore */ }
  };

  const handleExport = async () => {
    try {
      const res = await collectionsApi.exportCsv();
      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = 'collections_queue.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* ignore */ }
  };

  const handleBulkAssign = async () => {
    if (!assignAgent || selectedIds.size === 0) return;
    try {
      const caseIds = Array.from(selectedIds).map(appId => {
        const entry = queue.find(q => q.id === appId);
        return entry?.case_id;
      }).filter(Boolean) as number[];
      if (caseIds.length > 0) {
        await collectionsApi.bulkAssign({ case_ids: caseIds, agent_id: assignAgent });
      }
      setSelectedIds(new Set());
      setShowBulkAssign(false);
      await loadQueue();
    } catch { /* ignore */ }
  };

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortDir('desc');
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
    const pageItems = paginatedQueue;
    if (selectedIds.size === pageItems.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(pageItems.map(q => q.id)));
    }
  };

  const fmt = (val: number | null) =>
    val != null ? `TTD ${val.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '—';

  const severityBadge = (dpd: number) => {
    if (dpd >= 90) return { variant: 'danger' as const, label: '90+' };
    if (dpd >= 60) return { variant: 'warning' as const, label: '60+' };
    if (dpd >= 30) return { variant: 'warning' as const, label: '30+' };
    return { variant: 'info' as const, label: `${dpd}d` };
  };

  // Summary stats
  const totalOverdue = queue.reduce((sum, q) => sum + q.amount_due, 0);
  const severe = queue.filter(q => q.days_past_due >= 90).length;
  const moderate = queue.filter(q => q.days_past_due >= 30 && q.days_past_due < 90).length;
  const mild = queue.filter(q => q.days_past_due < 30).length;

  // Pagination
  const totalPages = Math.ceil(queue.length / PAGE_SIZE);
  const paginatedQueue = queue.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const inputClass = "h-[38px] px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-[var(--color-danger)]/15 rounded-lg">
            <AlertTriangle className="text-[var(--color-danger)]" size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Collections Queue</h1>
            <p className="text-sm text-[var(--color-text-muted)]">{queue.length} overdue accounts</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/backoffice/collections-dashboard">
            <Button variant="secondary">Dashboard</Button>
          </Link>
          <Button variant="secondary" onClick={handleExport}>
            <Download size={14} className="mr-1" /> Export CSV
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <div className="text-sm text-[var(--color-text-muted)]">Total Overdue</div>
          <div className="text-2xl font-bold text-[var(--color-danger)] mt-1">{fmt(totalOverdue)}</div>
        </Card>
        <Card>
          <div className="text-sm text-[var(--color-text-muted)]">Severe (90+ days)</div>
          <div className="text-2xl font-bold text-red-400 mt-1">{severe}</div>
        </Card>
        <Card>
          <div className="text-sm text-[var(--color-text-muted)]">Moderate (30-90)</div>
          <div className="text-2xl font-bold text-amber-400 mt-1">{moderate}</div>
        </Card>
        <Card>
          <div className="text-sm text-[var(--color-text-muted)]">Mild (&lt;30)</div>
          <div className="text-2xl font-bold text-yellow-400 mt-1">{mild}</div>
        </Card>
      </div>

      {/* Search & Filters */}
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
            <input
              type="text"
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(0); }}
              placeholder="Search name, reference, phone..."
              className={`${inputClass} w-full pl-9`}
            />
          </div>
          <select
            value={stage}
            onChange={e => { setStage(e.target.value); setPage(0); }}
            className={inputClass}
          >
            {STAGE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <select
            value={status}
            onChange={e => { setStatus(e.target.value); setPage(0); }}
            className={inputClass}
          >
            {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          {selectedIds.size > 0 && (
            <Button variant="secondary" onClick={() => setShowBulkAssign(!showBulkAssign)}>
              <Users size={14} className="mr-1" /> Assign ({selectedIds.size})
            </Button>
          )}
        </div>
        {showBulkAssign && selectedIds.size > 0 && (
          <div className="flex items-center gap-3 mt-3 pt-3 border-t border-[var(--color-border)]">
            <select
              value={assignAgent || ''}
              onChange={e => setAssignAgent(Number(e.target.value) || null)}
              className={inputClass}
            >
              <option value="">Select Agent</option>
              {agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
            <Button onClick={handleBulkAssign} disabled={!assignAgent}>Assign</Button>
            <Button variant="secondary" onClick={() => { setShowBulkAssign(false); setSelectedIds(new Set()); }}>Cancel</Button>
          </div>
        )}
      </Card>

      {/* Queue Table */}
      <Card padding="none">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                <th className="px-3 py-3 text-left">
                  <input
                    type="checkbox"
                    checked={selectedIds.size > 0 && selectedIds.size === paginatedQueue.length}
                    onChange={toggleSelectAll}
                    className="rounded"
                  />
                </th>
                <th className="px-3 py-3 text-left">Reference</th>
                <th className="px-3 py-3 text-left">Applicant</th>
                <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort('amount_due')}>
                  <span className="inline-flex items-center gap-1">
                    Amount Due <ArrowUpDown size={12} />
                  </span>
                </th>
                <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort('days_past_due')}>
                  <span className="inline-flex items-center gap-1">
                    DPD <ArrowUpDown size={12} />
                  </span>
                </th>
                <th className="px-3 py-3 text-left">Stage</th>
                <th className="px-3 py-3 text-left">Agent</th>
                <th className="px-3 py-3 text-left">NBA</th>
                <th className="px-3 py-3 text-left">Flags</th>
                <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort('priority_score')}>
                  <span className="inline-flex items-center gap-1">
                    Priority <ArrowUpDown size={12} />
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={10} className="py-12 text-center text-[var(--color-text-muted)]">
                    <RefreshCw className="animate-spin mx-auto mb-2" size={20} />Loading...
                  </td>
                </tr>
              ) : paginatedQueue.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-4 py-8 text-center text-[var(--color-text-muted)]">
                    No overdue accounts found
                  </td>
                </tr>
              ) : paginatedQueue.map(item => {
                const badge = severityBadge(item.days_past_due);
                const nba = item.next_best_action ? NBA_ICONS[item.next_best_action] : null;
                const NbaIcon = nba?.icon || AlertTriangle;
                return (
                  <tr
                    key={item.id}
                    className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] cursor-pointer transition-colors"
                    onClick={() => navigate(`/backoffice/collections/${item.id}`)}
                  >
                    <td className="px-3 py-3" onClick={e => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(item.id)}
                        onChange={() => toggleSelect(item.id)}
                        className="rounded"
                      />
                    </td>
                    <td className="px-3 py-3 font-mono text-xs text-[var(--color-primary)]">{item.reference_number}</td>
                    <td className="px-3 py-3" onClick={e => e.stopPropagation()}>
                      <Link to={`/backoffice/customers/${item.applicant_id}`} className="hover:text-[var(--color-primary)] transition-colors">
                        {item.applicant_name}
                      </Link>
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap font-bold text-[var(--color-danger)]">{fmt(item.amount_due)}</td>
                    <td className="px-3 py-3"><Badge variant={badge.variant}>{badge.label}</Badge></td>
                    <td className="px-3 py-3 text-xs capitalize">{item.delinquency_stage?.replace(/_/g, ' ') || '—'}</td>
                    <td className="px-3 py-3 text-xs">{item.assigned_agent_name || <span className="text-[var(--color-text-muted)]">Unassigned</span>}</td>
                    <td className="px-3 py-3">
                      {item.next_best_action ? (
                        <span className={`inline-flex items-center gap-1 text-xs font-medium ${nba?.color || 'text-[var(--color-text-muted)]'}`}>
                          <NbaIcon size={12} />
                          {nba?.label || item.next_best_action.replace(/_/g, ' ')}
                        </span>
                      ) : '—'}
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex gap-1">
                        {item.dispute_active && <span title="Dispute" className="w-2 h-2 rounded-full bg-purple-400" />}
                        {item.vulnerability_flag && <span title="Vulnerable" className="w-2 h-2 rounded-full bg-amber-400" />}
                        {item.do_not_contact && <span title="DNC" className="w-2 h-2 rounded-full bg-gray-400" />}
                        {item.hardship_flag && <span title="Hardship" className="w-2 h-2 rounded-full bg-blue-400" />}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-xs">{(item.priority_score * 100).toFixed(0)}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--color-border)]">
            <span className="text-xs text-[var(--color-text-muted)]">
              Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, queue.length)} of {queue.length}
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={page === 0}
                className="p-1 rounded hover:bg-[var(--color-surface-hover)] disabled:opacity-30"
              >
                <ChevronLeft size={16} />
              </button>
              {Array.from({ length: Math.min(totalPages, 7) }).map((_, i) => (
                <button
                  key={i}
                  onClick={() => setPage(i)}
                  className={`w-7 h-7 rounded text-xs ${
                    page === i ? 'bg-[var(--color-primary)] text-white' : 'hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]'
                  }`}
                >
                  {i + 1}
                </button>
              ))}
              <button
                onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="p-1 rounded hover:bg-[var(--color-surface-hover)] disabled:opacity-30"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
