import { useEffect, useState, useCallback, useMemo } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Clock,
  User,
  AlertTriangle,
  CheckCircle,
  Loader2,
  Search,
  RefreshCw,
  ArrowRight,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  TrendingUp,
  TrendingDown,
  Minus,
  Sparkles,
  Hand,
  X,
  Play,
  Users,
  Timer,
  Inbox,
  UserCheck,
  Hourglass,
  CircleDot,
  Brain,
  ClipboardList,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { getStatusBadge } from '../../../components/ui/Badge';
import { queueApi, underwriterApi } from '../../../api/endpoints';

/* ── Types ─────────────────────────────────────────── */

interface QueueItem {
  id: number;
  application_id: number;
  reference_number?: string;
  applicant_name?: string;
  applicant_id?: number;
  amount_requested?: number;
  term_months?: number;
  purpose?: string;
  loan_status?: string;
  submitted_at?: string;
  priority_score: number;
  priority_factors?: Record<string, any>;
  status: string;
  assigned_to_id?: number;
  assigned_to_name?: string;
  suggested_for_id?: number;
  claimed_by_id?: number;
  waiting_since?: string;
  waiting_reason?: string;
  sla_status?: string;
  sla_deadline?: string;
  return_count: number;
  is_stuck: boolean;
  is_flagged: boolean;
  flag_reasons?: string[];
  completeness_score?: number;
  complexity_estimate_hours?: number;
  channel?: string;
  created_at?: string;
  is_suggestion?: boolean;
}

interface AwarenessData {
  pending: number;
  waiting: number;
  avg_turnaround_hours?: number;
  my_active: number;
  my_decided_today: number;
  team: { user_id: number; name: string; load: number; max_load: number; available: boolean }[];
  config: {
    assignment_mode: string;
    stages_enabled: boolean;
    sla_mode: string;
    authority_limits_enabled: boolean;
    skills_routing_enabled: boolean;
    exceptions_formal: boolean;
  };
}

type Tab = 'shared' | 'my-queue' | 'waiting' | 'all';

/* ── All Applications Types ───────────────────── */

interface Application {
  id: number;
  reference_number: string;
  applicant_id: number;
  applicant_name: string | null;
  amount_requested: number;
  term_months: number;
  purpose: string;
  status: string;
  submitted_at: string | null;
  created_at: string;
  assigned_underwriter_id: number | null;
  assigned_underwriter_name: string | null;
}

type SortKey = 'reference_number' | 'applicant_name' | 'amount_requested' | 'term_months' | 'status' | 'assigned_underwriter_name' | 'created_at';
type SortDir = 'asc' | 'desc';

const STATUS_FILTERS = [
  { value: 'all', label: 'All Statuses' },
  { value: '', label: 'All Active' },
  { value: 'draft', label: 'Draft' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'under_review', label: 'Under Review' },
  { value: 'credit_check', label: 'Credit Check' },
  { value: 'decision_pending', label: 'Decision Pending' },
  { value: 'awaiting_documents', label: 'Awaiting Documents' },
  { value: 'approved', label: 'Approved' },
  { value: 'declined', label: 'Declined' },
  { value: 'offer_sent', label: 'Offer Sent' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'counter_proposed', label: 'Counter Proposed' },
  { value: 'disbursed', label: 'Disbursed' },
  { value: 'rejected_by_applicant', label: 'Rejected by Applicant' },
  { value: 'cancelled', label: 'Cancelled' },
];

const ALL_COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'reference_number', label: 'Reference' },
  { key: 'applicant_name', label: 'Applicant' },
  { key: 'amount_requested', label: 'Amount' },
  { key: 'term_months', label: 'Term' },
  { key: 'status', label: 'Status' },
  { key: 'assigned_underwriter_name', label: 'Assigned To' },
  { key: 'created_at', label: 'Date' },
];

/* ── Helpers ───────────────────────────────────────── */

function timeAgo(iso?: string): string {
  if (!iso) return '-';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

function slaColor(status?: string): string {
  if (status === 'breached') return 'text-red-400';
  if (status === 'warning') return 'text-amber-400';
  if (status === 'paused') return 'text-gray-400';
  return 'text-green-400';
}

function priorityBar(score: number): string {
  const pct = Math.min(100, Math.max(5, score * 100));
  if (pct > 70) return 'bg-red-500';
  if (pct > 50) return 'bg-amber-500';
  if (pct > 30) return 'bg-sky-500';
  return 'bg-gray-500';
}

const trendIcon = (trend: string) => {
  if (trend === 'growing') return <TrendingUp size={14} className="text-red-400" />;
  if (trend === 'shrinking') return <TrendingDown size={14} className="text-green-400" />;
  return <Minus size={14} className="text-gray-400" />;
};

/* ── Component ─────────────────────────────────────── */

export default function SmartQueue() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const urlTab = searchParams.get('tab');
  const urlStatusFilter = searchParams.get('status_filter');
  const [activeTab, setActiveTab] = useState<Tab>(urlTab === 'all' || urlStatusFilter ? 'all' : 'shared');
  const [items, setItems] = useState<QueueItem[]>([]);
  const [_total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [awareness, setAwareness] = useState<AwarenessData | null>(null);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');
  const [claimingId, setClaimingId] = useState<number | null>(null);
  const [explainText, setExplainText] = useState<string | null>(null);
  const [explainEntryId, setExplainEntryId] = useState<number | null>(null);

  /* ── All Applications state ───────────────── */
  const [allApps, setAllApps] = useState<Application[]>([]);
  const [allAppsLoading, setAllAppsLoading] = useState(false);
  const [allAppsFilter, setAllAppsFilter] = useState(urlStatusFilter || 'all');
  const [allAppsSearch, setAllAppsSearch] = useState('');
  const [allSortKey, setAllSortKey] = useState<SortKey>('created_at');
  const [allSortDir, setAllSortDir] = useState<SortDir>('desc');

  /* ── Loaders ───────────────────────────────── */

  const loadAwareness = useCallback(async () => {
    try {
      const res = await queueApi.getAwareness();
      setAwareness(res.data);
    } catch { /* silent */ }
  }, []);

  const loadQueue = useCallback(async () => {
    try {
      setLoading(true);
      let res;
      if (activeTab === 'shared') {
        res = await queueApi.getSharedQueue({ limit: 100 });
      } else if (activeTab === 'my-queue') {
        res = await queueApi.getMyQueue();
      } else {
        res = await queueApi.getWaiting();
      }
      setItems(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch {
      setError('Failed to load queue');
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => { loadAwareness(); }, [loadAwareness]);
  useEffect(() => { if (activeTab !== 'all') loadQueue(); }, [loadQueue, activeTab]);

  /* ── All Applications loader ──────────────── */
  const loadAllApps = useCallback(() => {
    setAllAppsLoading(true);
    const params = allAppsFilter === 'all' ? 'all' : allAppsFilter || undefined;
    underwriterApi.getQueue(params)
      .then((res) => setAllApps(res.data))
      .catch(() => {})
      .finally(() => setAllAppsLoading(false));
  }, [allAppsFilter]);

  useEffect(() => { if (activeTab === 'all') loadAllApps(); }, [activeTab, loadAllApps]);

  /* ── Actions ───────────────────────────────── */

  const handleClaim = async (item: QueueItem) => {
    try {
      setClaimingId(item.id);
      await queueApi.claimEntry(item.id);
      navigate(`/backoffice/review/${item.application_id}`);
    } catch (err: any) {
      if (err?.response?.status === 409) {
        setError('Already claimed by another user. Refreshing...');
        loadQueue();
      } else {
        setError('Failed to claim');
      }
    } finally {
      setClaimingId(null);
    }
  };

  const handleRelease = async (id: number) => {
    try {
      await queueApi.releaseEntry(id);
      loadQueue();
      loadAwareness();
    } catch { setError('Failed to release'); }
  };

  const handleBorrowerResponded = async (id: number) => {
    try {
      await queueApi.borrowerResponded(id);
      loadQueue();
    } catch { setError('Failed to update'); }
  };

  const handleDefer = async (id: number) => {
    try {
      await queueApi.deferEntry(id);
      loadQueue();
    } catch { setError('Failed to defer'); }
  };

  const handleNeedHelp = async () => {
    if (!awareness) return;
    try {
      const myId = awareness.team.find(t => t.load > 0)?.user_id;
      if (myId) {
        await queueApi.needHelp(myId);
        loadQueue();
        loadAwareness();
      }
    } catch { setError('Failed to request help'); }
  };

  const handleExplain = async (entryId: number) => {
    if (explainEntryId === entryId) { setExplainEntryId(null); setExplainText(null); return; }
    try {
      setExplainEntryId(entryId);
      const res = await queueApi.explainPriority(entryId);
      setExplainText(res.data.explanation);
    } catch { setExplainText('Could not generate explanation.'); }
  };

  /* ── All Applications sort/filter ─────────── */

  const handleAllSort = (key: SortKey) => {
    if (allSortKey === key) {
      setAllSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setAllSortKey(key);
      setAllSortDir(key === 'created_at' || key === 'amount_requested' ? 'desc' : 'asc');
    }
  };

  const allSortIcon = (key: SortKey) => {
    if (allSortKey !== key) return <ArrowUpDown size={12} className="ml-1 opacity-30" />;
    return allSortDir === 'asc'
      ? <ArrowUp size={12} className="ml-1 text-[var(--color-primary)]" />
      : <ArrowDown size={12} className="ml-1 text-[var(--color-primary)]" />;
  };

  const displayedApps = useMemo(() => {
    const q = allAppsSearch.trim().toLowerCase();
    let list = allApps;
    if (q) {
      list = list.filter(app => {
        const name = (app.applicant_name || '').toLowerCase();
        const ref = app.reference_number.toLowerCase();
        const idStr = String(app.id);
        return name.includes(q) || ref.includes(q) || idStr.includes(q);
      });
    }
    return [...list].sort((a, b) => {
      let aVal: string | number = '';
      let bVal: string | number = '';
      switch (allSortKey) {
        case 'reference_number': aVal = a.reference_number; bVal = b.reference_number; break;
        case 'applicant_name': aVal = (a.applicant_name || '').toLowerCase(); bVal = (b.applicant_name || '').toLowerCase(); break;
        case 'amount_requested': aVal = a.amount_requested; bVal = b.amount_requested; break;
        case 'term_months': aVal = a.term_months; bVal = b.term_months; break;
        case 'status': aVal = a.status; bVal = b.status; break;
        case 'assigned_underwriter_name': aVal = (a.assigned_underwriter_name || '').toLowerCase(); bVal = (b.assigned_underwriter_name || '').toLowerCase(); break;
        case 'created_at': aVal = a.created_at || ''; bVal = b.created_at || ''; break;
      }
      if (aVal < bVal) return allSortDir === 'asc' ? -1 : 1;
      if (aVal > bVal) return allSortDir === 'asc' ? 1 : -1;
      return 0;
    });
  }, [allApps, allAppsSearch, allSortKey, allSortDir]);

  const handleAssign = async (id: number) => {
    await underwriterApi.assign(id);
    loadAllApps();
  };

  /* ── Filtered items ────────────────────────── */

  const displayed = search.trim()
    ? items.filter(item => {
        const q = search.toLowerCase();
        return (
          (item.reference_number || '').toLowerCase().includes(q) ||
          (item.applicant_name || '').toLowerCase().includes(q) ||
          String(item.application_id).includes(q)
        );
      })
    : items;

  const config = awareness?.config;

  /* ── Render ────────────────────────────────── */

  const tabs: { id: Tab; label: string; icon: React.ReactNode; count?: number }[] = [
    { id: 'shared', label: 'Work Queue', icon: <Inbox size={15} />, count: awareness?.pending },
    { id: 'my-queue', label: 'My Queue', icon: <UserCheck size={15} />, count: awareness?.my_active },
    { id: 'waiting', label: 'Waiting', icon: <Hourglass size={15} />, count: awareness?.waiting },
    { id: 'all', label: 'All Applications', icon: <ClipboardList size={15} /> },
  ];

  return (
    <div className="space-y-4">
      {/* ── Ambient Stats Bar ── */}
      {awareness && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[
            { label: 'Pending', value: awareness.pending, icon: <Inbox size={15} className="text-sky-400" />, sub: trendIcon('stable') },
            { label: 'My Active', value: awareness.my_active, icon: <UserCheck size={15} className="text-green-400" /> },
            { label: 'Decided Today', value: awareness.my_decided_today, icon: <CheckCircle size={15} className="text-emerald-400" /> },
            { label: 'Avg Turnaround', value: awareness.avg_turnaround_hours ? `${awareness.avg_turnaround_hours}h` : '-', icon: <Timer size={15} className="text-amber-400" /> },
            { label: 'Team Online', value: awareness.team.filter(t => t.available).length, icon: <Users size={15} className="text-purple-400" /> },
          ].map((stat, i) => (
            <div key={i} className="px-3 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]">
              <div className="flex items-center gap-1.5 mb-0.5">{stat.icon}<span className="text-[10px] text-[var(--color-text-muted)]">{stat.label}</span></div>
              <div className="text-lg font-bold">{stat.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── Header + Actions ── */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Applications Queue</h1>
        <div className="flex items-center gap-2">
          {config?.assignment_mode !== 'pull' && (
            <Button size="sm" variant="ghost" onClick={handleNeedHelp}>
              <Hand size={14} className="mr-1" /> Need Help
            </Button>
          )}
          <Button size="sm" variant="secondary" onClick={() => { loadQueue(); loadAwareness(); }}>
            <RefreshCw size={14} className="mr-1" /> Refresh
          </Button>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-2 rounded-lg text-sm flex items-center gap-2">
          <AlertTriangle size={14} /> {error}
          <button onClick={() => setError('')} className="ml-auto"><X size={12} /></button>
        </div>
      )}

      {/* ── Tabs ── */}
      <div className="flex gap-1 border-b border-[var(--color-border)]">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-[var(--color-primary)] text-[var(--color-primary)]'
                : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
            }`}
          >
            {tab.icon} {tab.label}
            {tab.count != null && tab.count > 0 && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--color-primary)]/10 text-[var(--color-primary)]">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── All Applications Tab ── */}
      {activeTab === 'all' ? (
        <div>
          {/* Search + filter bar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 mb-4">
            <div className="relative flex-1">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
              <input
                type="text"
                value={allAppsSearch}
                onChange={e => setAllAppsSearch(e.target.value)}
                placeholder="Search by name, reference or ID..."
                className="w-full pl-9 pr-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none"
              />
            </div>
            <select
              value={allAppsFilter}
              onChange={e => setAllAppsFilter(e.target.value)}
              className="px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none"
            >
              {STATUS_FILTERS.map(f => (
                <option key={f.value} value={f.value}>{f.label}</option>
              ))}
            </select>
          </div>

          {/* Count */}
          <p className="text-sm text-[var(--color-text-muted)] mb-3">
            {displayedApps.length}{displayedApps.length !== allApps.length ? ` of ${allApps.length}` : ''} application{allApps.length !== 1 ? 's' : ''}
          </p>

          {/* Table */}
          <Card padding="none">
            {allAppsLoading ? (
              <div className="flex items-center justify-center h-40 text-[var(--color-text-muted)]">
                <Loader2 className="animate-spin mr-2" size={20} /> Loading applications...
              </div>
            ) : displayedApps.length === 0 ? (
              <p className="text-center py-8 text-[var(--color-text-muted)]">
                {allAppsSearch ? 'No applications match your search' : 'No applications found'}
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--color-border)]">
                      {ALL_COLUMNS.map(({ key, label }) => (
                        <th
                          key={key}
                          onClick={() => handleAllSort(key)}
                          className="text-left py-3 px-4 text-[var(--color-text-muted)] font-medium text-xs uppercase tracking-wider cursor-pointer select-none hover:text-[var(--color-text)] transition-colors"
                        >
                          <span className="inline-flex items-center">
                            {label}
                            {allSortIcon(key)}
                          </span>
                        </th>
                      ))}
                      <th className="text-left py-3 px-4 text-[var(--color-text-muted)] font-medium text-xs uppercase tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayedApps.map(app => (
                      <tr key={app.id} className="border-b border-[var(--color-border)]/50 hover:bg-[var(--color-surface-hover)] transition-colors">
                        <td className="py-3 px-4 font-medium">
                          <Link to={`/backoffice/review/${app.id}`} className="text-[var(--color-primary)] hover:text-[var(--color-primary-light)] transition-colors">
                            {app.reference_number}
                          </Link>
                        </td>
                        <td className="py-3 px-4 text-[var(--color-text)]">
                          <Link to={`/backoffice/customers/${app.applicant_id}`} className="hover:text-[var(--color-primary)] transition-colors">
                            {app.applicant_name || '—'}
                          </Link>
                        </td>
                        <td className="py-3 px-4 text-[var(--color-text)] font-medium">TTD {app.amount_requested.toLocaleString()}</td>
                        <td className="py-3 px-4 text-[var(--color-text-muted)]">{app.term_months}m</td>
                        <td className="py-3 px-4">{getStatusBadge(app.status)}</td>
                        <td className="py-3 px-4 text-[var(--color-text-muted)]">
                          {app.assigned_underwriter_name ? (
                            <span className="inline-flex items-center gap-1 text-xs">
                              <span className="w-1.5 h-1.5 rounded-full bg-green-400 shrink-0" />
                              {app.assigned_underwriter_name}
                            </span>
                          ) : (
                            <span className="text-xs text-[var(--color-text-muted)] opacity-40">Unassigned</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-[var(--color-text-muted)]">
                          {new Date(app.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}{' '}
                          {new Date(app.created_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex items-center space-x-2">
                            <Link to={`/backoffice/review/${app.id}`}>
                              <Button size="sm" variant="outline">Review</Button>
                            </Link>
                            {!app.assigned_underwriter_id && app.status === 'submitted' && (
                              <Button size="sm" variant="ghost" onClick={() => handleAssign(app.id)}>
                                Assign
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      ) : (
      <>
      {/* ── Search ── */}
      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search by name, reference or ID..."
          className="w-full pl-9 pr-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none"
        />
      </div>

      {/* ── Queue List ── */}
      {loading ? (
        <div className="flex items-center justify-center h-40 text-[var(--color-text-muted)]">
          <Loader2 className="animate-spin mr-2" size={20} /> Loading queue...
        </div>
      ) : displayed.length === 0 ? (
        <Card>
          <p className="text-sm text-[var(--color-text-muted)] text-center py-12">
            {activeTab === 'shared' ? 'No applications in the queue. Everything is caught up!' :
             activeTab === 'my-queue' ? 'Nothing assigned to you. Grab one from the Work Queue.' :
             'No applications waiting for borrower response.'}
          </p>
        </Card>
      ) : (
        <div className="space-y-1.5">
          {displayed.map((item, _idx) => (
            <div
              key={item.id}
              className={`group rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] hover:border-[var(--color-primary)]/40 transition-all ${
                item.is_stuck ? 'border-l-2 border-l-amber-500' : ''
              } ${item.sla_status === 'breached' ? 'border-l-2 border-l-red-500' : ''}`}
            >
              <div className="flex items-center gap-3 px-4 py-3">
                {/* Priority indicator */}
                <div className="w-1 h-10 rounded-full overflow-hidden bg-gray-700 shrink-0">
                  <div className={`w-full ${priorityBar(item.priority_score)} transition-all`} style={{ height: `${Math.min(100, item.priority_score * 100)}%` }} />
                </div>

                {/* Main info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm truncate">{item.applicant_name || 'Unknown'}</span>
                    <span className="text-xs font-mono text-[var(--color-text-muted)]">{item.reference_number}</span>
                    {item.is_suggestion && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/30">Suggested</span>
                    )}
                    {item.is_stuck && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30">Stuck</span>
                    )}
                    {item.return_count > 0 && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/30">Returned</span>
                    )}
                    {item.is_flagged && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/30">Flagged</span>
                    )}
                    {item.assigned_to_name && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 flex items-center gap-0.5">
                        <User size={9} /> {item.assigned_to_name}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5 text-xs text-[var(--color-text-muted)]">
                    {item.amount_requested && <span className="font-medium text-[var(--color-text)]">TTD {item.amount_requested.toLocaleString()}</span>}
                    {item.purpose && <span>{item.purpose.replace(/_/g, ' ')}</span>}
                    {item.term_months && <span>{item.term_months}m</span>}
                    {item.completeness_score != null && (
                      <span className={item.completeness_score > 80 ? 'text-green-400' : item.completeness_score > 50 ? 'text-amber-400' : 'text-red-400'}>
                        {item.completeness_score.toFixed(0)}% complete
                      </span>
                    )}
                  </div>
                </div>

                {/* Time waiting */}
                <div className="text-right shrink-0">
                  <div className={`text-sm font-medium ${config?.sla_mode !== 'none' ? slaColor(item.sla_status) : 'text-[var(--color-text-muted)]'}`}>
                    <Clock size={12} className="inline mr-0.5" />
                    {timeAgo(activeTab === 'waiting' ? item.waiting_since : item.submitted_at || item.created_at)}
                  </div>
                  {activeTab === 'waiting' && item.waiting_reason && (
                    <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5 truncate max-w-[120px]">{item.waiting_reason}</div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1 shrink-0">
                  {activeTab === 'shared' && (
                    <button
                      onClick={() => handleClaim(item)}
                      disabled={claimingId === item.id}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-[var(--color-primary)] text-white hover:opacity-90 transition-opacity disabled:opacity-50"
                    >
                      {claimingId === item.id ? <Loader2 size={12} className="animate-spin" /> : <ArrowRight size={12} />}
                      Work
                    </button>
                  )}
                  {activeTab === 'my-queue' && !item.is_suggestion && (
                    <>
                      <button onClick={() => navigate(`/backoffice/review/${item.application_id}`)}
                        className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-[var(--color-primary)] text-white hover:opacity-90">
                        <ArrowRight size={12} /> Continue
                      </button>
                      <button onClick={() => handleRelease(item.id)} className="p-1.5 rounded hover:bg-red-500/10 text-red-400" title="Release">
                        <X size={14} />
                      </button>
                    </>
                  )}
                  {activeTab === 'my-queue' && item.is_suggestion && (
                    <>
                      <button onClick={() => handleClaim(item)}
                        className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs font-medium bg-green-600 text-white hover:opacity-90">
                        <CheckCircle size={12} /> Accept
                      </button>
                      <button onClick={() => handleDefer(item.id)}
                        className="p-1.5 rounded hover:bg-gray-500/10 text-[var(--color-text-muted)]" title="Defer">
                        <X size={14} />
                      </button>
                    </>
                  )}
                  {activeTab === 'waiting' && (
                    <button onClick={() => handleBorrowerResponded(item.id)}
                      className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs font-medium bg-green-600 text-white hover:opacity-90">
                      <Play size={12} /> Responded
                    </button>
                  )}
                  <button
                    onClick={() => handleExplain(item.id)}
                    className="p-1.5 rounded hover:bg-purple-500/10 text-purple-400"
                    title="Explain priority"
                  >
                    <Brain size={14} />
                  </button>
                </div>
              </div>

              {/* Explain panel */}
              {explainEntryId === item.id && explainText && (
                <div className="px-4 pb-3 border-t border-[var(--color-border)] mx-4 pt-2">
                  <div className="flex items-start gap-2 text-xs">
                    <Sparkles size={14} className="text-purple-400 shrink-0 mt-0.5" />
                    <p className="text-[var(--color-text-muted)]">{explainText}</p>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── Team Workload (ambient, always visible at bottom) ── */}
      {awareness && awareness.team.length > 0 && (
        <Card>
          <h3 className="text-xs font-medium text-[var(--color-text-muted)] mb-2 flex items-center gap-1.5">
            <Users size={13} /> Team Workload
          </h3>
          <div className="flex flex-wrap gap-2">
            {awareness.team.map(m => (
              <div key={m.user_id} className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs border ${
                !m.available ? 'opacity-40 border-gray-600' :
                m.load >= m.max_load ? 'border-red-500/30 text-red-400' :
                m.load === 0 ? 'border-green-500/30 text-green-400' :
                'border-[var(--color-border)] text-[var(--color-text-muted)]'
              }`}>
                <CircleDot size={8} className={m.available ? (m.load === 0 ? 'text-green-400' : 'text-sky-400') : 'text-gray-500'} />
                <span>{m.name.split(' ')[0]}</span>
                <span className="font-mono">{m.load}/{m.max_load}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
      </>
      )}
    </div>
  );
}
