import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Search, Download, ChevronLeft, ChevronRight,
  ArrowUpDown, ArrowUp, ArrowDown, ArrowRight,
  Shield, ShieldAlert, Phone, MessageCircle, Smartphone,
  Gavel, Scale, UserCheck, Users, AlertCircle, Heart,
  RefreshCw, X, Filter, Sparkles, ChevronDown, ChevronUp,
  Lightbulb, TrendingUp, StickyNote, Clock,
  FileText, MailWarning, PhoneCall,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Badge from '../../../components/ui/Badge';
import Button from '../../../components/ui/Button';
import { collectionsApi, underwriterApi } from '../../../api/endpoints';

/* ─────────────────────────── Types ─────────────────────────── */

interface CollectionQueueEntry {
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
  nba_reasoning: string | null;
  dispute_active: boolean;
  vulnerability_flag: boolean;
  do_not_contact: boolean;
  hardship_flag: boolean;
  priority_score: number;
  employer_name: string | null;
  sector: string | null;
  sector_risk_rating: string | null;
  product_type: string | null;
  ptp_status: string | null;
  ptp_amount: number | null;
  ptp_date: string | null;
  last_contact_channel: string | null;
  last_contact_outcome: string | null;
  sla_deadline: string | null;
  sla_hours_remaining: number | null;
  propensity_score: number | null;
  propensity_trend: 'improving' | 'stable' | 'declining' | null;
}

interface DailyBriefing {
  date: string;
  portfolio_summary: { total_cases: number; total_overdue: number };
  priorities: string[];
  changes: string[];
  strategy_tip: string;
}

/* ─────────────────────── Constants ─────────────────────────── */

const PAGE_SIZE = 25;

const currencyFmt = new Intl.NumberFormat('en-TT', {
  style: 'currency',
  currency: 'TTD',
  minimumFractionDigits: 2,
});

const dateFmt = (iso: string | null) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('en-TT', { day: '2-digit', month: 'short' });
};

const STAGE_OPTIONS = [
  { value: '', label: 'All DPD' },
  { value: 'early_1_30', label: '1–30 days' },
  { value: 'mid_31_60', label: '31–60 days' },
  { value: 'late_61_90', label: '61–90 days' },
  { value: 'severe_90_plus', label: '90+ days' },
];

const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'settled', label: 'Settled' },
  { value: 'legal', label: 'Legal' },
];

const PTP_OPTIONS = [
  { value: '', label: 'All PTP' },
  { value: 'kept', label: 'Kept' },
  { value: 'pending', label: 'Pending' },
  { value: 'broken', label: 'Broken' },
  { value: 'none', label: 'None' },
];

const NBA_ACTION_OPTIONS = [
  { value: '', label: 'All AI Actions' },
  { value: 'send_whatsapp_reminder', label: 'WhatsApp Reminder' },
  { value: 'send_sms_reminder', label: 'SMS Reminder' },
  { value: 'call_now', label: 'Call Now' },
  { value: 'escalate_supervisor', label: 'Escalate Supervisor' },
  { value: 'escalate_field', label: 'Field Visit' },
  { value: 'send_demand_letter', label: 'Demand Letter' },
  { value: 'escalate_legal', label: 'Legal' },
  { value: 'hold_dispute', label: 'Dispute Hold' },
  { value: 'hold_do_not_contact', label: 'DNC Hold' },
  { value: 'hold_vulnerability_review', label: 'Vulnerability' },
  { value: 'offer_hardship_plan', label: 'Hardship Plan' },
];

const SECTOR_OPTIONS = [
  { value: '', label: 'All Sectors' },
  { value: 'retail', label: 'Retail' },
  { value: 'construction', label: 'Construction' },
  { value: 'agriculture', label: 'Agriculture' },
  { value: 'energy', label: 'Energy' },
  { value: 'services', label: 'Services' },
  { value: 'manufacturing', label: 'Manufacturing' },
  { value: 'government', label: 'Government' },
  { value: 'other', label: 'Other' },
];

/* PRODUCT_TYPE_OPTIONS hidden — single product (hire-purchase) for now */

const PROPENSITY_OPTIONS = [
  { value: '', label: 'All Propensity' },
  { value: 'high', label: 'High (70-100)' },
  { value: 'medium', label: 'Medium (40-69)' },
  { value: 'low', label: 'Low (0-39)' },
];

const SLA_STATUS_OPTIONS = [
  { value: '', label: 'All SLA' },
  { value: 'on_track', label: 'On Track' },
  { value: 'at_risk', label: 'At Risk' },
  { value: 'breached', label: 'Breached' },
];

const FLAGS_OPTIONS = [
  { value: '', label: 'All Flags' },
  { value: 'dispute', label: 'Dispute Active' },
  { value: 'vulnerability', label: 'Vulnerability' },
  { value: 'dnc', label: 'Do Not Contact' },
  { value: 'hardship', label: 'Hardship' },
];

const SORT_OPTIONS = [
  { value: 'priority_score', label: 'Priority Score' },
  { value: 'days_past_due', label: 'Days Past Due' },
  { value: 'amount_due', label: 'Amount Due' },
  { value: 'outstanding_balance', label: 'Outstanding Balance' },
  { value: 'propensity_score', label: 'Propensity Score' },
  { value: 'sla_hours_remaining', label: 'SLA Time Left' },
];

type NbaKey =
  | 'send_whatsapp_reminder' | 'send_sms_reminder' | 'call_now'
  | 'escalate_supervisor' | 'escalate_field' | 'send_demand_letter'
  | 'escalate_legal' | 'hold_dispute' | 'hold_do_not_contact'
  | 'hold_vulnerability_review' | 'offer_hardship_plan';

const NBA_ICONS: Record<NbaKey, { icon: typeof Phone; color: string; bg: string; label: string }> = {
  send_whatsapp_reminder:    { icon: MessageCircle, color: '#22c55e', bg: 'rgba(34,197,94,0.12)',  label: 'WhatsApp' },
  send_sms_reminder:         { icon: Smartphone,    color: '#3b82f6', bg: 'rgba(59,130,246,0.12)', label: 'SMS' },
  call_now:                  { icon: Phone,         color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', label: 'Call Now' },
  escalate_supervisor:       { icon: UserCheck,     color: '#f97316', bg: 'rgba(249,115,22,0.12)', label: 'Escalate Sup.' },
  escalate_field:            { icon: Users,         color: '#f97316', bg: 'rgba(249,115,22,0.12)', label: 'Field Visit' },
  send_demand_letter:        { icon: Gavel,         color: '#ef4444', bg: 'rgba(239,68,68,0.12)',  label: 'Demand Letter' },
  escalate_legal:            { icon: Scale,         color: '#ef4444', bg: 'rgba(239,68,68,0.12)',  label: 'Legal' },
  hold_dispute:              { icon: ShieldAlert,   color: '#9ca3af', bg: 'rgba(156,163,175,0.12)', label: 'Dispute Hold' },
  hold_do_not_contact:       { icon: Shield,        color: '#9ca3af', bg: 'rgba(156,163,175,0.12)', label: 'DNC' },
  hold_vulnerability_review: { icon: AlertCircle,   color: '#a855f7', bg: 'rgba(168,85,247,0.12)', label: 'Vulnerability' },
  offer_hardship_plan:       { icon: Heart,         color: '#ec4899', bg: 'rgba(236,72,153,0.12)', label: 'Hardship Plan' },
};

const CHANNEL_ICONS: Record<string, typeof Phone> = {
  phone: PhoneCall,
  whatsapp: MessageCircle,
  sms: Smartphone,
  email: MailWarning,
  letter: FileText,
};

/* ─────────────────────── Helpers ───────────────────────────── */

function priorityColor(score: number): string {
  if (score > 0.8) return '#ef4444';
  if (score > 0.6) return '#f97316';
  if (score > 0.4) return '#eab308';
  if (score > 0.2) return '#22c55e';
  return '#6b7280';
}

function dpdColor(dpd: number): string {
  if (dpd > 90) return '#ef4444';
  if (dpd > 60) return '#ea580c';
  if (dpd > 30) return '#f97316';
  if (dpd >= 1) return '#f59e0b';
  return '#6b7280';
}

function ptpBadgeVariant(status: string | null): 'success' | 'warning' | 'danger' | 'default' {
  if (status === 'kept') return 'success';
  if (status === 'pending') return 'warning';
  if (status === 'broken') return 'danger';
  return 'default';
}

function slaColor(hours: number | null): string {
  if (hours === null) return '#6b7280';
  if (hours < 0) return '#000000';
  if (hours < 1) return '#ef4444';
  if (hours < 4) return '#f59e0b';
  return '#22c55e';
}

function slaDisplay(hours: number | null): string {
  if (hours === null) return '—';
  if (hours < 0) return 'BREACHED';
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  return `${hours.toFixed(1)}h`;
}

function PropensityTrendIcon({ trend }: { trend: string | null }) {
  if (trend === 'improving') return <ArrowUp size={12} className="text-emerald-400" />;
  if (trend === 'declining') return <ArrowDown size={12} className="text-red-400" />;
  return <ArrowRight size={12} className="text-[var(--color-text-muted)]" />;
}

function sectorRiskBadgeVariant(rating: string | null): 'success' | 'warning' | 'danger' | 'default' {
  if (rating === 'low') return 'success';
  if (rating === 'medium') return 'warning';
  if (rating === 'high') return 'danger';
  return 'default';
}

/* ────────────────── Styled select (inline) ────────────────── */

const selectClass =
  'h-[32px] px-2 py-0 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-xs text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)] cursor-pointer appearance-none pr-6';

/* ────────────────────── Tooltip ────────────────────────────── */

function Tooltip({ text, children }: { text: string; children: React.ReactNode }) {
  const [show, setShow] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  return (
    <div
      className="relative inline-flex"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      ref={ref}
    >
      {children}
      {show && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 pointer-events-none">
          <div
            className="px-3 py-2 rounded-lg text-xs max-w-[260px] whitespace-pre-wrap shadow-xl"
            style={{
              background: 'var(--color-bg)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-text)',
            }}
          >
            {text}
          </div>
        </div>
      )}
    </div>
  );
}

/* ════════════════════════ MAIN COMPONENT ═══════════════════════ */

export default function Collections() {
  const navigate = useNavigate();

  /* ── Queue state ────────────────────────────────────────────── */
  const [queue, setQueue] = useState<CollectionQueueEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);

  /* ── Filter state ───────────────────────────────────────────── */
  const [search, setSearch] = useState('');
  const [stage, setStage] = useState('');
  const [status, setStatus] = useState('');
  const [ptpStatus, setPtpStatus] = useState('');
  const [nbaAction, setNbaAction] = useState('');
  const [sector, setSector] = useState('');
  const [productType] = useState('');
  const [propensityBand, setPropensityBand] = useState('');
  const [slaStatus, setSlaStatus] = useState('');
  const [flagsFilter, setFlagsFilter] = useState('');
  const [agentId, setAgentId] = useState('');
  const [sortBy, setSortBy] = useState('priority_score');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(0);

  /* ── Selection state ────────────────────────────────────────── */
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [hoveredRow, setHoveredRow] = useState<number | null>(null);

  /* ── Agents ─────────────────────────────────────────────────── */
  const [agents, setAgents] = useState<Array<{ id: number; name: string }>>([]);
  const [bulkAssignAgent, setBulkAssignAgent] = useState<number | null>(null);
  const [showBulkPanel, setShowBulkPanel] = useState(false);
  const [assigning, setAssigning] = useState(false);

  /* ── Briefing ───────────────────────────────────────────────── */
  const [briefing, setBriefing] = useState<DailyBriefing | null>(null);
  const [briefingLoading, setBriefingLoading] = useState(true);
  const [briefingOpen, setBriefingOpen] = useState(true);

  /* ── WhatsApp modal ─────────────────────────────────────────── */
  const [waEntry, setWaEntry] = useState<CollectionQueueEntry | null>(null);
  const [waMessage, setWaMessage] = useState('');
  const [waDrafting, setWaDrafting] = useState(false);
  const [waSending, setWaSending] = useState(false);

  /* ── Syncing / exporting ────────────────────────────────────── */
  const [syncing, setSyncing] = useState(false);

  /* ── Search debounce ────────────────────────────────────────── */
  const searchTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const [debouncedSearch, setDebouncedSearch] = useState('');

  useEffect(() => {
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => setDebouncedSearch(search), 350);
    return () => clearTimeout(searchTimer.current);
  }, [search]);

  /* ── Load queue ─────────────────────────────────────────────── */
  const loadQueue = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = {
        sort_by: sortBy,
        sort_dir: sortDir,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      };
      if (debouncedSearch) params.search = debouncedSearch;
      if (stage) params.stage = stage;
      if (status) params.status = status;
      if (ptpStatus) params.ptp_status = ptpStatus;
      if (nbaAction) params.nba_action = nbaAction;
      if (sector) params.sector = sector;
      if (productType) params.product_type = productType;
      if (propensityBand) params.propensity_band = propensityBand;
      if (slaStatus) params.sla_status = slaStatus;
      if (agentId) params.agent_id = agentId;

      const res = await collectionsApi.getQueue(params);
      const data = Array.isArray(res.data) ? res.data : res.data?.items ?? res.data?.results ?? [];
      setQueue(data);
      setTotal(res.data?.total ?? res.data?.count ?? data.length);
    } catch {
      /* silently fail */
    }
    setLoading(false);
  }, [debouncedSearch, stage, status, ptpStatus, nbaAction, sector, productType, propensityBand, slaStatus, agentId, sortBy, sortDir, page]);

  useEffect(() => { loadQueue(); }, [loadQueue]);

  /* ── Load agents ────────────────────────────────────────────── */
  useEffect(() => {
    (async () => {
      try {
        const res = await underwriterApi.getStaff();
        const list = Array.isArray(res.data) ? res.data : res.data?.items ?? [];
        setAgents(list.map((u: any) => ({ id: u.id, name: `${u.first_name} ${u.last_name}` })));
      } catch { /* ignore */ }
    })();
  }, []);

  /* ── Load briefing ──────────────────────────────────────────── */
  useEffect(() => {
    (async () => {
      setBriefingLoading(true);
      try {
        const res = await collectionsApi.getDailyBriefing();
        setBriefing(res.data);
      } catch { /* ignore */ }
      setBriefingLoading(false);
    })();
  }, []);

  /* ── Computed portfolio stats (from current page or total) ──── */
  const stats = useMemo(() => {
    const dpd1_30 = queue.filter(q => q.days_past_due >= 1 && q.days_past_due <= 30).length;
    const dpd31_60 = queue.filter(q => q.days_past_due >= 31 && q.days_past_due <= 60).length;
    const dpd61_90 = queue.filter(q => q.days_past_due >= 61 && q.days_past_due <= 90).length;
    const dpd90plus = queue.filter(q => q.days_past_due > 90).length;
    const totalOverdue = queue.reduce((s, q) => s + q.amount_due, 0);
    return { dpd1_30, dpd31_60, dpd61_90, dpd90plus, totalOverdue };
  }, [queue]);

  /* ── Handlers ───────────────────────────────────────────────── */
  const resetPage = () => setPage(0);

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

  const handleSync = async () => {
    setSyncing(true);
    try {
      await collectionsApi.syncCases();
      await loadQueue();
    } catch { /* ignore */ }
    setSyncing(false);
  };

  const handleBulkAssign = async () => {
    if (!bulkAssignAgent || selectedIds.size === 0) return;
    setAssigning(true);
    try {
      const caseIds = Array.from(selectedIds)
        .map(id => queue.find(q => q.id === id)?.case_id)
        .filter(Boolean) as number[];
      if (caseIds.length > 0) {
        await collectionsApi.bulkAssign({ case_ids: caseIds, agent_id: bulkAssignAgent });
      }
      setSelectedIds(new Set());
      setShowBulkPanel(false);
      setBulkAssignAgent(null);
      await loadQueue();
    } catch { /* ignore */ }
    setAssigning(false);
  };

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === queue.length && queue.length > 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(queue.map(q => q.id)));
    }
  };

  const handleQuickWhatsApp = async (entry: CollectionQueueEntry) => {
    setWaEntry(entry);
    setWaMessage('');
    setWaDrafting(true);
    try {
      const res = await collectionsApi.draftMessage({
        case_id: entry.case_id!,
        channel: 'whatsapp',
        template_type: 'reminder',
      });
      setWaMessage(res.data.message || '');
    } catch { setWaMessage(''); }
    setWaDrafting(false);
  };

  const sendWhatsApp = async () => {
    if (!waEntry || !waMessage) return;
    setWaSending(true);
    try {
      await collectionsApi.sendWhatsApp(waEntry.applicant_id, { message: waMessage });
    } catch { /* ignore */ }
    setWaSending(false);
    setWaEntry(null);
  };

  /* ── Active filters (for pills) ─────────────────────────────── */
  const activeFilters = useMemo(() => {
    const pills: { key: string; label: string; clear: () => void }[] = [];
    if (stage) pills.push({ key: 'stage', label: `DPD: ${STAGE_OPTIONS.find(o => o.value === stage)?.label}`, clear: () => { setStage(''); resetPage(); } });
    if (status) pills.push({ key: 'status', label: `Status: ${STATUS_OPTIONS.find(o => o.value === status)?.label}`, clear: () => { setStatus(''); resetPage(); } });
    if (ptpStatus) pills.push({ key: 'ptp', label: `PTP: ${PTP_OPTIONS.find(o => o.value === ptpStatus)?.label}`, clear: () => { setPtpStatus(''); resetPage(); } });
    if (nbaAction) pills.push({ key: 'nba', label: `AI: ${NBA_ACTION_OPTIONS.find(o => o.value === nbaAction)?.label}`, clear: () => { setNbaAction(''); resetPage(); } });
    if (sector) pills.push({ key: 'sector', label: `Sector: ${SECTOR_OPTIONS.find(o => o.value === sector)?.label}`, clear: () => { setSector(''); resetPage(); } });
    if (propensityBand) pills.push({ key: 'propensity', label: `Propensity: ${PROPENSITY_OPTIONS.find(o => o.value === propensityBand)?.label}`, clear: () => { setPropensityBand(''); resetPage(); } });
    if (slaStatus) pills.push({ key: 'sla', label: `SLA: ${SLA_STATUS_OPTIONS.find(o => o.value === slaStatus)?.label}`, clear: () => { setSlaStatus(''); resetPage(); } });
    if (flagsFilter) pills.push({ key: 'flags', label: `Flag: ${FLAGS_OPTIONS.find(o => o.value === flagsFilter)?.label}`, clear: () => { setFlagsFilter(''); resetPage(); } });
    if (agentId) pills.push({ key: 'agent', label: `Agent: ${agents.find(a => a.id === Number(agentId))?.name || agentId}`, clear: () => { setAgentId(''); resetPage(); } });
    return pills;
  }, [stage, status, ptpStatus, nbaAction, sector, productType, propensityBand, slaStatus, flagsFilter, agentId, agents]);

  const clearAllFilters = () => {
    setSearch(''); setStage(''); setStatus(''); setPtpStatus(''); setNbaAction('');
    setSector(''); setPropensityBand(''); setSlaStatus('');
    setFlagsFilter(''); setAgentId(''); resetPage();
  };

  /* ── Pagination ──────────────────────────────────────────────── */
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  /* ── Client-side flag filter (applied to queue already fetched) */
  const filteredQueue = useMemo(() => {
    if (!flagsFilter) return queue;
    return queue.filter(q => {
      if (flagsFilter === 'dispute') return q.dispute_active;
      if (flagsFilter === 'vulnerability') return q.vulnerability_flag;
      if (flagsFilter === 'dnc') return q.do_not_contact;
      if (flagsFilter === 'hardship') return q.hardship_flag;
      return true;
    });
  }, [queue, flagsFilter]);

  /* ═══════════════════════ RENDER ══════════════════════════════ */
  return (
    <div className="space-y-4">
      {/* ──────────── 1. TOP STATS BAR ──────────── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <h1 className="text-xl font-bold mr-2">Collections Queue</h1>
          <span
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
          >
            <span className="text-[var(--color-text-muted)]">Total</span>
            <span className="font-bold">{total}</span>
          </span>
          <span
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
            style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}
          >
            <span className="text-red-400">Overdue</span>
            <span className="font-bold text-red-400">{currencyFmt.format(stats.totalOverdue)}</span>
          </span>
          <span
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
            style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)' }}
          >
            <span style={{ color: '#f59e0b' }}>1-30d</span>
            <span className="font-bold" style={{ color: '#f59e0b' }}>{stats.dpd1_30}</span>
          </span>
          <span
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
            style={{ background: 'rgba(249,115,22,0.08)', border: '1px solid rgba(249,115,22,0.2)' }}
          >
            <span style={{ color: '#f97316' }}>31-60d</span>
            <span className="font-bold" style={{ color: '#f97316' }}>{stats.dpd31_60}</span>
          </span>
          <span
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
            style={{ background: 'rgba(234,88,12,0.08)', border: '1px solid rgba(234,88,12,0.2)' }}
          >
            <span style={{ color: '#ea580c' }}>61-90d</span>
            <span className="font-bold" style={{ color: '#ea580c' }}>{stats.dpd61_90}</span>
          </span>
          <span
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
            style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}
          >
            <span className="text-red-400">90+d</span>
            <span className="font-bold text-red-400">{stats.dpd90plus}</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={handleSync} disabled={syncing}>
            <RefreshCw size={14} className={syncing ? 'animate-spin mr-1' : 'mr-1'} />
            {syncing ? 'Syncing...' : 'Sync'}
          </Button>
          <Button variant="ghost" size="sm" onClick={handleExport}>
            <Download size={14} className="mr-1" /> Export
          </Button>
        </div>
      </div>

      {/* ──────────── 2. AI DAILY BRIEFING ──────────── */}
      <Card padding="none">
        <button
          className="w-full flex items-center justify-between px-5 py-3 text-left hover:bg-[var(--color-bg)]/30 transition-colors"
          onClick={() => setBriefingOpen(!briefingOpen)}
        >
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-amber-400" />
            <span className="font-semibold text-sm">AI Daily Briefing</span>
            {briefing && (
              <span className="text-xs text-[var(--color-text-muted)]">
                — {new Date(briefing.date).toLocaleDateString('en-TT', { weekday: 'long', month: 'short', day: 'numeric' })}
              </span>
            )}
          </div>
          {briefingOpen ? <ChevronUp size={16} className="text-[var(--color-text-muted)]" /> : <ChevronDown size={16} className="text-[var(--color-text-muted)]" />}
        </button>

        {briefingOpen && (
          <div className="px-5 pb-4 border-t border-[var(--color-border)]">
            {briefingLoading ? (
              <div className="flex items-center gap-2 py-4 text-sm text-[var(--color-text-muted)]">
                <RefreshCw size={14} className="animate-spin" /> Loading briefing...
              </div>
            ) : briefing ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4">
                {/* Priorities */}
                <div>
                  <h4 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-2 flex items-center gap-1">
                    <AlertCircle size={12} /> Priorities
                  </h4>
                  <ul className="space-y-1.5">
                    {briefing.priorities.map((p, i) => (
                      <li key={i} className="text-sm flex items-start gap-2">
                        <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                        {p}
                      </li>
                    ))}
                  </ul>
                </div>
                {/* Changes */}
                <div>
                  <h4 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-2 flex items-center gap-1">
                    <TrendingUp size={12} /> Changes
                  </h4>
                  <ul className="space-y-1.5">
                    {briefing.changes.map((c, i) => (
                      <li key={i} className="text-sm flex items-start gap-2">
                        <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-sky-400 flex-shrink-0" />
                        {c}
                      </li>
                    ))}
                  </ul>
                </div>
                {/* Strategy Tip */}
                <div>
                  <h4 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-2 flex items-center gap-1">
                    <Lightbulb size={12} /> Strategy Tip
                  </h4>
                  <p className="text-sm leading-relaxed">{briefing.strategy_tip}</p>
                </div>
              </div>
            ) : (
              <p className="py-4 text-sm text-[var(--color-text-muted)]">Briefing unavailable.</p>
            )}
            {briefing && !briefingLoading && (
              <div className="flex justify-end pt-3">
                <Button size="sm" variant="ghost" onClick={() => setBriefingOpen(false)}>
                  Got it
                </Button>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* ──────────── 3. FILTER BAR ──────────── */}
      <Card padding="sm">
        {/* Search */}
        <div className="relative mb-3">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
          <input
            type="text"
            value={search}
            onChange={e => { setSearch(e.target.value); resetPage(); }}
            placeholder="Search by name, reference, phone, employer..."
            className="w-full h-[36px] pl-9 pr-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)] placeholder:text-[var(--color-text-muted)]"
          />
          {search && (
            <button className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--color-text)]" onClick={() => { setSearch(''); resetPage(); }}>
              <X size={14} />
            </button>
          )}
        </div>

        {/* Filter Row */}
        <div className="flex flex-wrap items-center gap-2">
          <Filter size={14} className="text-[var(--color-text-muted)]" />

          <select value={stage} onChange={e => { setStage(e.target.value); resetPage(); }} className={selectClass}>
            {STAGE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>

          <select value={nbaAction} onChange={e => { setNbaAction(e.target.value); resetPage(); }} className={selectClass}>
            {NBA_ACTION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>

          <select value={ptpStatus} onChange={e => { setPtpStatus(e.target.value); resetPage(); }} className={selectClass}>
            {PTP_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>

          <select value={sector} onChange={e => { setSector(e.target.value); resetPage(); }} className={selectClass}>
            {SECTOR_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>

          <select value={flagsFilter} onChange={e => { setFlagsFilter(e.target.value); resetPage(); }} className={selectClass}>
            {FLAGS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>

          <select value={slaStatus} onChange={e => { setSlaStatus(e.target.value); resetPage(); }} className={selectClass}>
            {SLA_STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>

          <select value={propensityBand} onChange={e => { setPropensityBand(e.target.value); resetPage(); }} className={selectClass}>
            {PROPENSITY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>

          <select value={agentId} onChange={e => { setAgentId(e.target.value); resetPage(); }} className={selectClass}>
            <option value="">All Agents</option>
            {agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>

          {/* Sort */}
          <div className="ml-auto flex items-center gap-1">
            <select value={sortBy} onChange={e => { setSortBy(e.target.value); resetPage(); }} className={selectClass}>
              {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <button
              onClick={() => setSortDir(d => d === 'asc' ? 'desc' : 'asc')}
              className="h-[32px] w-[32px] flex items-center justify-center rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] hover:bg-[var(--color-surface)] transition-colors"
              title={sortDir === 'asc' ? 'Ascending' : 'Descending'}
            >
              {sortDir === 'asc' ? <ArrowUp size={14} /> : <ArrowDown size={14} />}
            </button>
          </div>
        </div>

        {/* Active filter pills + bulk assign */}
        {(activeFilters.length > 0 || selectedIds.size > 0) && (
          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-[var(--color-border)] flex-wrap">
            {activeFilters.map(f => (
              <span
                key={f.key}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
                style={{ background: 'var(--color-primary)', color: '#fff' }}
              >
                {f.label}
                <button onClick={f.clear} className="hover:opacity-70"><X size={12} /></button>
              </span>
            ))}
            {activeFilters.length > 1 && (
              <button onClick={clearAllFilters} className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] underline">
                Clear all
              </button>
            )}
            {selectedIds.size > 0 && (
              <div className="ml-auto flex items-center gap-2">
                <span className="text-xs text-[var(--color-text-muted)]">{selectedIds.size} selected</span>
                <Button size="sm" variant="secondary" onClick={() => setShowBulkPanel(!showBulkPanel)}>
                  <Users size={12} className="mr-1" /> Bulk Assign
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Bulk assign panel */}
        {showBulkPanel && selectedIds.size > 0 && (
          <div className="flex items-center gap-3 mt-3 pt-3 border-t border-[var(--color-border)]">
            <span className="text-xs text-[var(--color-text-muted)]">Assign {selectedIds.size} cases to:</span>
            <select
              value={bulkAssignAgent || ''}
              onChange={e => setBulkAssignAgent(Number(e.target.value) || null)}
              className={selectClass}
            >
              <option value="">Select Agent</option>
              {agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
            <Button size="sm" onClick={handleBulkAssign} disabled={!bulkAssignAgent || assigning} isLoading={assigning}>
              Assign
            </Button>
            <Button size="sm" variant="ghost" onClick={() => { setShowBulkPanel(false); setSelectedIds(new Set()); }}>
              Cancel
            </Button>
          </div>
        )}
      </Card>

      {/* ──────────── 4. MAIN QUEUE TABLE ──────────── */}
      <Card padding="none">
        <div className="overflow-x-auto">
          <table className="w-full text-sm" style={{ minWidth: '1400px' }}>
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] text-xs uppercase tracking-wider">
                <th className="px-3 py-3 w-10 text-left">
                  <input
                    type="checkbox"
                    checked={selectedIds.size > 0 && selectedIds.size === filteredQueue.length}
                    onChange={toggleSelectAll}
                    className="rounded cursor-pointer"
                  />
                </th>
                <th className="px-2 py-3 w-14 text-center">#</th>
                <th className="px-3 py-3 text-left min-w-[180px]">Borrower</th>
                <SortHeader field="days_past_due" label="DPD" current={sortBy} dir={sortDir} onClick={(f) => { setSortBy(f); setSortDir(d => sortBy === f ? (d === 'asc' ? 'desc' : 'asc') : 'desc'); resetPage(); }} />
                <SortHeader field="outstanding_balance" label="Balance" current={sortBy} dir={sortDir} onClick={(f) => { setSortBy(f); setSortDir(d => sortBy === f ? (d === 'asc' ? 'desc' : 'asc') : 'desc'); resetPage(); }} />
                <SortHeader field="amount_due" label="Arrears" current={sortBy} dir={sortDir} onClick={(f) => { setSortBy(f); setSortDir(d => sortBy === f ? (d === 'asc' ? 'desc' : 'asc') : 'desc'); resetPage(); }} />
                <th className="px-3 py-3 text-left">AI Action</th>
                <th className="px-3 py-3 text-left">PTP</th>
                <th className="px-3 py-3 text-left">Last Contact</th>
                <SortHeader field="sla_hours_remaining" label="SLA" current={sortBy} dir={sortDir} onClick={(f) => { setSortBy(f); setSortDir(d => sortBy === f ? (d === 'asc' ? 'desc' : 'asc') : 'desc'); resetPage(); }} />
                <th className="px-3 py-3 text-left">Sector</th>
                <SortHeader field="propensity_score" label="Propensity" current={sortBy} dir={sortDir} onClick={(f) => { setSortBy(f); setSortDir(d => sortBy === f ? (d === 'asc' ? 'desc' : 'asc') : 'desc'); resetPage(); }} />
                <th className="px-2 py-3 w-24 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={14} className="py-16 text-center text-[var(--color-text-muted)]">
                    <RefreshCw className="animate-spin mx-auto mb-2" size={20} />
                    <p className="text-sm">Loading queue...</p>
                  </td>
                </tr>
              ) : filteredQueue.length === 0 ? (
                <tr>
                  <td colSpan={14} className="py-16 text-center text-[var(--color-text-muted)]">
                    <Search className="mx-auto mb-2 opacity-40" size={24} />
                    <p className="text-sm">No cases found</p>
                    {activeFilters.length > 0 && (
                      <button onClick={clearAllFilters} className="mt-2 text-xs text-[var(--color-primary)] hover:underline">
                        Clear filters
                      </button>
                    )}
                  </td>
                </tr>
              ) : filteredQueue.map((item, idx) => {
                const nba = item.next_best_action ? NBA_ICONS[item.next_best_action as NbaKey] : null;
                const NbaIcon = nba?.icon || AlertCircle;
                const isHovered = hoveredRow === item.id;
                const ChannelIcon = item.last_contact_channel ? (CHANNEL_ICONS[item.last_contact_channel] || Phone) : null;
                const rank = page * PAGE_SIZE + idx + 1;

                return (
                  <tr
                    key={item.id}
                    className="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/40 transition-colors cursor-pointer"
                    onClick={() => navigate(`/backoffice/collections/${item.id}`)}
                    onMouseEnter={() => setHoveredRow(item.id)}
                    onMouseLeave={() => setHoveredRow(null)}
                  >
                    {/* Checkbox */}
                    <td className="px-3 py-2.5" onClick={e => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(item.id)}
                        onChange={() => toggleSelect(item.id)}
                        className="rounded cursor-pointer"
                      />
                    </td>

                    {/* Priority Rank */}
                    <td className="px-2 py-2.5 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        <span
                          className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                          style={{ backgroundColor: priorityColor(item.priority_score) }}
                        />
                        <span className="text-xs font-bold text-[var(--color-text-muted)]">{rank}</span>
                      </div>
                    </td>

                    {/* Borrower */}
                    <td className="px-3 py-2.5" onClick={e => e.stopPropagation()}>
                      <Link
                        to={`/backoffice/collections/${item.id}`}
                        className="font-medium hover:text-[var(--color-primary)] transition-colors text-sm block leading-tight"
                      >
                        {item.applicant_name}
                      </Link>
                      {item.employer_name && (
                        <span className="text-[10px] text-[var(--color-text-muted)] block mt-0.5">{item.employer_name}</span>
                      )}
                      {/* Flag dots */}
                      <div className="flex gap-1 mt-1">
                        {item.dispute_active && <span title="Dispute Active" className="w-1.5 h-1.5 rounded-full bg-purple-400" />}
                        {item.vulnerability_flag && <span title="Vulnerable" className="w-1.5 h-1.5 rounded-full bg-amber-400" />}
                        {item.do_not_contact && <span title="Do Not Contact" className="w-1.5 h-1.5 rounded-full bg-gray-400" />}
                        {item.hardship_flag && <span title="Hardship" className="w-1.5 h-1.5 rounded-full bg-pink-400" />}
                      </div>
                    </td>

                    {/* DPD */}
                    <td className="px-3 py-2.5">
                      <span
                        className="inline-flex items-center justify-center px-2 py-0.5 rounded-md text-xs font-bold"
                        style={{
                          backgroundColor: `${dpdColor(item.days_past_due)}18`,
                          color: dpdColor(item.days_past_due),
                        }}
                      >
                        {item.days_past_due}d
                      </span>
                    </td>

                    {/* Balance */}
                    <td className="px-3 py-2.5 whitespace-nowrap text-xs font-medium">
                      {currencyFmt.format(item.outstanding_balance)}
                    </td>

                    {/* Arrears */}
                    <td className="px-3 py-2.5 whitespace-nowrap text-xs font-bold text-red-400">
                      {currencyFmt.format(item.amount_due)}
                    </td>

                    {/* AI Action */}
                    <td className="px-3 py-2.5">
                      {item.next_best_action && nba ? (
                        <Tooltip text={item.nba_reasoning || `${nba.label} (${((item.nba_confidence ?? 0) * 100).toFixed(0)}% confidence)`}>
                          <span
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium"
                            style={{ backgroundColor: nba.bg, color: nba.color }}
                          >
                            <NbaIcon size={12} />
                            {nba.label}
                          </span>
                        </Tooltip>
                      ) : (
                        <span className="text-xs text-[var(--color-text-muted)]">—</span>
                      )}
                    </td>

                    {/* PTP Status */}
                    <td className="px-3 py-2.5">
                      {item.ptp_status ? (
                        <Badge variant={ptpBadgeVariant(item.ptp_status)}>
                          {item.ptp_status}
                        </Badge>
                      ) : (
                        <span className="text-xs text-[var(--color-text-muted)]">none</span>
                      )}
                    </td>

                    {/* Last Contact */}
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1.5 text-xs">
                        <span className="text-[var(--color-text-muted)]">{dateFmt(item.last_contact)}</span>
                        {ChannelIcon && <ChannelIcon size={11} className="text-[var(--color-text-muted)]" />}
                        {item.last_contact_outcome && (
                          <span className="text-[10px] text-[var(--color-text-muted)] capitalize">
                            {item.last_contact_outcome.replace(/_/g, ' ')}
                          </span>
                        )}
                      </div>
                    </td>

                    {/* SLA Timer */}
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1">
                        <Clock size={11} style={{ color: slaColor(item.sla_hours_remaining) }} />
                        <span
                          className="text-xs font-bold"
                          style={{ color: slaColor(item.sla_hours_remaining) }}
                        >
                          {slaDisplay(item.sla_hours_remaining)}
                        </span>
                      </div>
                    </td>

                    {/* Sector */}
                    <td className="px-3 py-2.5">
                      {item.sector ? (
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs capitalize">{item.sector}</span>
                          {item.sector_risk_rating && (
                            <Badge variant={sectorRiskBadgeVariant(item.sector_risk_rating)}>
                              {item.sector_risk_rating}
                            </Badge>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs text-[var(--color-text-muted)]">—</span>
                      )}
                    </td>

                    {/* Propensity */}
                    <td className="px-3 py-2.5">
                      {item.propensity_score != null ? (
                        <div className="flex items-center gap-1">
                          <span className="text-xs font-bold">{item.propensity_score}</span>
                          <PropensityTrendIcon trend={item.propensity_trend} />
                        </div>
                      ) : (
                        <span className="text-xs text-[var(--color-text-muted)]">—</span>
                      )}
                    </td>

                    {/* Quick Actions */}
                    <td className="px-2 py-2.5" onClick={e => e.stopPropagation()}>
                      <div
                        className="flex items-center gap-1 transition-opacity"
                        style={{ opacity: isHovered ? 1 : 0 }}
                      >
                        {/* Quick Call */}
                        {item.phone && (
                          <a
                            href={`tel:${item.phone}`}
                            className="p-1.5 rounded-md hover:bg-[var(--color-bg)] transition-colors"
                            title={`Call ${item.phone}`}
                            onClick={e => e.stopPropagation()}
                          >
                            <Phone size={13} className="text-emerald-400" />
                          </a>
                        )}
                        {/* Quick WhatsApp */}
                        {item.case_id && (
                          <button
                            className="p-1.5 rounded-md hover:bg-[var(--color-bg)] transition-colors"
                            title="Quick WhatsApp"
                            onClick={e => { e.stopPropagation(); handleQuickWhatsApp(item); }}
                          >
                            <MessageCircle size={13} className="text-green-400" />
                          </button>
                        )}
                        {/* Quick Note */}
                        <button
                          className="p-1.5 rounded-md hover:bg-[var(--color-bg)] transition-colors"
                          title="Quick Note"
                          onClick={e => { e.stopPropagation(); navigate(`/backoffice/collections/${item.id}?tab=notes`); }}
                        >
                          <StickyNote size={13} className="text-amber-400" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* ──────────── 6. PAGINATION ──────────── */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--color-border)]">
          <span className="text-xs text-[var(--color-text-muted)]">
            {filteredQueue.length > 0 ? (
              <>Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}</>
            ) : (
              'No results'
            )}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium border border-[var(--color-border)] bg-[var(--color-bg)] hover:bg-[var(--color-surface)] disabled:opacity-30 transition-colors"
            >
              <ChevronLeft size={14} /> Previous
            </button>
            <span className="px-3 text-xs text-[var(--color-text-muted)]">
              Page {page + 1} of {totalPages}
            </span>
            <button
              onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium border border-[var(--color-border)] bg-[var(--color-bg)] hover:bg-[var(--color-surface)] disabled:opacity-30 transition-colors"
            >
              Next <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </Card>

      {/* ──────────── WHATSAPP MODAL ──────────── */}
      {waEntry && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setWaEntry(null)}>
          <div
            className="w-full max-w-lg rounded-xl border shadow-2xl mx-4"
            style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]">
              <div className="flex items-center gap-2">
                <MessageCircle size={18} className="text-green-400" />
                <h3 className="font-semibold text-sm">WhatsApp — {waEntry.applicant_name}</h3>
              </div>
              <button onClick={() => setWaEntry(null)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                <X size={18} />
              </button>
            </div>
            <div className="p-5">
              {waDrafting ? (
                <div className="flex items-center gap-2 py-8 justify-center text-sm text-[var(--color-text-muted)]">
                  <Sparkles size={14} className="animate-pulse text-amber-400" /> AI drafting message...
                </div>
              ) : (
                <textarea
                  value={waMessage}
                  onChange={e => setWaMessage(e.target.value)}
                  rows={5}
                  className="w-full p-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)] resize-none"
                  placeholder="Type your message..."
                />
              )}
            </div>
            <div className="flex justify-end gap-2 px-5 py-4 border-t border-[var(--color-border)]">
              <Button variant="ghost" size="sm" onClick={() => setWaEntry(null)}>Cancel</Button>
              <Button size="sm" onClick={sendWhatsApp} disabled={!waMessage || waSending} isLoading={waSending}>
                <MessageCircle size={14} className="mr-1" /> Send WhatsApp
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════ SUB-COMPONENTS ═══════════════════════════ */

function SortHeader({
  field, label, current, dir, onClick,
}: {
  field: string;
  label: string;
  current: string;
  dir: 'asc' | 'desc';
  onClick: (field: string) => void;
}) {
  const active = current === field;
  return (
    <th
      className="px-3 py-3 text-left cursor-pointer select-none hover:text-[var(--color-text)] transition-colors"
      onClick={() => onClick(field)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {active ? (
          dir === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />
        ) : (
          <ArrowUpDown size={10} className="opacity-40" />
        )}
      </span>
    </th>
  );
}
