import { useEffect, useState, useRef, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, Phone, Mail, MessageCircle, Send, Plus,
  ShieldAlert, AlertCircle, AlertTriangle, Clock,
  CheckCircle, XCircle, X,
  DollarSign, FileText, Handshake,
  TrendingUp, TrendingDown, Calendar, CreditCard,
  Activity, Target, Flag, Edit, Zap, Brain,
  Building, MessageSquare, BarChart3, RefreshCw, Sparkles,
  type LucideIcon,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import Badge from '../../../components/ui/Badge';
import { collectionsApi } from '../../../api/endpoints';

/* ═══════════════════════════════════════════════════════════
   Type Definitions
   ═══════════════════════════════════════════════════════════ */

interface BorrowerInfo {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  whatsapp_number: string;
  mobile_phone: string;
  employer_name: string;
  employer_sector: string;
  job_title: string;
}

interface ProfileInfo {
  monthly_income: number;
  monthly_expenses: number;
  [key: string]: unknown;
}

interface SectorRisk {
  sector: string;
  risk_rating: string;
}

interface CaseInfo {
  id: number;
  loan_application_id: number;
  status: string;
  delinquency_stage: string;
  dpd: number;
  total_overdue: number;
  priority_score: number;
  assigned_agent_id: number | null;
  assigned_agent_name: string | null;
  dispute_active: boolean;
  vulnerability_flag: boolean;
  do_not_contact: boolean;
  hardship_flag: boolean;
  first_contact_at: string | null;
  last_contact_at: string | null;
  sla_first_contact_deadline: string | null;
  sla_next_contact_deadline: string | null;
  created_at: string;
}

interface LoanInfo {
  id: number;
  reference_number: string;
  amount_requested: number;
  amount_approved: number;
  term_months: number;
  interest_rate: number;
  monthly_payment: number;
  purpose: string;
  disbursed_at: string;
  status: string;
}

interface ArrearItem {
  installment: number;
  due_date: string;
  amount_overdue: number;
}

interface BalanceBreakdown {
  total_principal: number;
  total_interest: number;
  total_fees: number;
  arrears_breakdown: ArrearItem[];
}

interface ScheduleItem {
  id: number;
  installment_number: number;
  due_date: string;
  principal: number;
  interest: number;
  fee: number;
  amount_due: number;
  amount_paid: number;
  status: string;
}

interface PaymentItem {
  id: number;
  amount: number;
  payment_date: string;
  payment_type: string;
  status: string;
  reference_number: string;
}

interface InteractionItem {
  id: number;
  channel: string;
  notes: string;
  action_taken: string;
  outcome: string;
  agent_name: string;
  next_action_date: string | null;
  promise_amount: number | null;
  promise_date: string | null;
  created_at: string;
}

interface ChatItem {
  id: number | string;
  direction: string;
  message: string;
  status: string;
  created_at: string;
}

interface PtpItem {
  id: number;
  amount_promised: number;
  promise_date: string;
  payment_method: string;
  status: string;
  amount_received: number;
  agent_name: string;
  notes: string | null;
  broken_at: string | null;
  created_at: string;
}

interface SettlementItem {
  id: number;
  offer_type: string;
  original_balance: number;
  settlement_amount: number;
  discount_pct: number;
  plan_months: number | null;
  plan_monthly_amount: number | null;
  lump_sum: number | null;
  status: string;
  notes: string | null;
  created_at: string;
}

interface HeatmapItem {
  month: string;
  status: 'on_time' | 'late' | 'missed' | 'none';
}

interface NbaSuggestedOffer {
  offer_type?: string;
  settlement_amount?: number;
  discount_pct?: number;
  plan_months?: number;
  plan_monthly_amount?: number;
  lump_sum?: number;
}

interface NbaInfo {
  action: string;
  confidence: number;
  reasoning: string;
  timing: string;
  best_channel: string;
  best_number: string;
  suggested_offer: string | NbaSuggestedOffer;
  confidence_label: string;
  tone_guidance?: string;
}

interface PropensityInfo {
  score: number;
  trend: string;
  factors_positive: string[];
  factors_negative: string[];
}

interface PatternItem {
  category: string;
  insight: string;
}

interface RiskSignal {
  severity: string;
  category: string;
  signal: string;
}

interface SimilarOutcomes {
  dpd_band: string;
  total_similar: number;
  cured: number;
  cure_rate: number;
  avg_resolution_days: number;
  description: string;
}

interface AiData {
  nba: NbaInfo;
  propensity: PropensityInfo;
  patterns: PatternItem[];
  risk_signals: RiskSignal[];
  similar_outcomes: SimilarOutcomes;
}

interface CaseFullData {
  borrower: BorrowerInfo;
  profile: ProfileInfo;
  sector_risk: SectorRisk;
  case: CaseInfo;
  loan: LoanInfo;
  balance_breakdown: BalanceBreakdown;
  schedules: ScheduleItem[];
  payments: PaymentItem[];
  interactions: InteractionItem[];
  chats: ChatItem[];
  ptps: PtpItem[];
  active_ptp: PtpItem | null;
  settlements: SettlementItem[];
  payment_heatmap: HeatmapItem[];
  ai: AiData;
}

interface TimelineEntry {
  id: string;
  type: 'interaction' | 'chat' | 'payment' | 'system';
  subType: string;
  timestamp: string;
  title: string;
  content: string;
  agent?: string;
}

/* ═══════════════════════════════════════════════════════════
   Helpers
   ═══════════════════════════════════════════════════════════ */

const fmtCurrency = (val: number | null | undefined): string => {
  if (val == null) return '—';
  return `TTD ${new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(val)}`;
};

const fmtShortDate = (dateStr: string): string => {
  const d = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

const timeAgo = (dateStr: string): string => {
  const d = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return d.toLocaleDateString();
};

const getDpdColor = (dpd: number): string => {
  if (dpd <= 0) return 'text-emerald-400';
  if (dpd <= 30) return 'text-amber-400';
  if (dpd <= 60) return 'text-orange-400';
  if (dpd <= 90) return 'text-orange-500';
  return 'text-red-500';
};

const getUrgencyBorder = (timing?: string): string => {
  if (!timing) return 'border-l-[var(--color-border)]';
  const t = timing.toLowerCase();
  if (t.includes('immediate') || t.includes('urgent') || t.includes('now'))
    return '!border-l-red-500';
  if (t.includes('today') || t.includes('asap'))
    return '!border-l-amber-500';
  if (t.includes('week') || t.includes('soon'))
    return '!border-l-sky-500';
  return 'border-l-[var(--color-border)]';
};

const getConfidenceVariant = (
  label: string,
): 'success' | 'warning' | 'danger' | 'info' => {
  switch (label.toLowerCase()) {
    case 'high':
      return 'success';
    case 'medium':
      return 'warning';
    case 'low':
      return 'danger';
    default:
      return 'info';
  }
};

const getPropensityColor = (score: number): string => {
  if (score >= 60) return 'text-emerald-400';
  if (score >= 30) return 'text-amber-400';
  return 'text-red-400';
};

const getPropensityBarColor = (score: number): string => {
  if (score >= 60) return 'bg-emerald-500';
  if (score >= 30) return 'bg-amber-500';
  return 'bg-red-500';
};

const getHeatmapColor = (status: string): string => {
  switch (status) {
    case 'on_time':
      return 'bg-emerald-500/30 text-emerald-300';
    case 'late':
      return 'bg-amber-500/30 text-amber-300';
    case 'missed':
      return 'bg-red-500/30 text-red-300';
    default:
      return 'bg-gray-700/40 text-gray-500';
  }
};

const getTimelineIcon = (type: string, subType?: string) => {
  switch (type) {
    case 'interaction':
      switch (subType) {
        case 'phone':
          return <Phone size={14} className="text-sky-400" />;
        case 'whatsapp':
          return <MessageCircle size={14} className="text-emerald-400" />;
        case 'email':
          return <Mail size={14} className="text-cyan-400" />;
        case 'sms':
          return <MessageSquare size={14} className="text-purple-400" />;
        default:
          return <Phone size={14} className="text-[var(--color-text-muted)]" />;
      }
    case 'chat':
      return <MessageCircle size={14} className="text-emerald-400" />;
    case 'payment':
      return <DollarSign size={14} className="text-emerald-400" />;
    case 'system':
      if (subType === 'ptp')
        return <Handshake size={14} className="text-amber-400" />;
      if (subType === 'settlement')
        return <FileText size={14} className="text-sky-400" />;
      return <Zap size={14} className="text-[var(--color-text-muted)]" />;
    default:
      return <Activity size={14} className="text-[var(--color-text-muted)]" />;
  }
};

const getTimelineIconBg = (type: string, subType?: string): string => {
  switch (type) {
    case 'interaction':
      switch (subType) {
        case 'phone':
          return 'bg-sky-500/15';
        case 'whatsapp':
          return 'bg-emerald-500/15';
        case 'email':
          return 'bg-cyan-500/15';
        case 'sms':
          return 'bg-purple-500/15';
        default:
          return 'bg-[var(--color-bg)]';
      }
    case 'chat':
      return 'bg-emerald-500/15';
    case 'payment':
      return 'bg-emerald-500/15';
    case 'system':
      return 'bg-amber-500/15';
    default:
      return 'bg-[var(--color-bg)]';
  }
};

const getNbaActionLabel = (action?: string): string => {
  if (!action) return 'Execute';
  return action
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
};

const inputCls =
  'w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]';

const inputSmCls =
  'w-full h-[30px] px-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded text-xs text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]';

/* ═══════════════════════════════════════════════════════════
   Component
   ═══════════════════════════════════════════════════════════ */

export default function CollectionDetail() {
  const { id } = useParams<{ id: string }>();
  const appId = parseInt(id || '0');

  /* ── State ── */
  const [data, setData] = useState<CaseFullData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Communication
  const [commTab, setCommTab] = useState<'whatsapp' | 'sms' | 'note'>('whatsapp');
  const [whatsappMsg, setWhatsappMsg] = useState('');
  const [smsMsg, setSmsMsg] = useState('');
  const [noteText, setNoteText] = useState('');
  const [noteCategory, setNoteCategory] = useState('general');
  const [sending, setSending] = useState(false);
  const [draftLoading, setDraftLoading] = useState(false);

  // Timeline
  const [timelineFilter, setTimelineFilter] = useState('all');

  // Override NBA modal
  const [showOverride, setShowOverride] = useState(false);
  const [overrideAction, setOverrideAction] = useState('');
  const [overrideReason, setOverrideReason] = useState('');

  // PTP form
  const [showPtpForm, setShowPtpForm] = useState(false);
  const [ptpForm, setPtpForm] = useState({
    amount_promised: '',
    promise_date: '',
    payment_method: '',
    notes: '',
  });

  /* ── Refs ── */
  const dataRef = useRef<CaseFullData | null>(null);
  const draftLoadedRef = useRef(false);
  const timelineRef = useRef<HTMLDivElement>(null);

  // Keep ref in sync for keyboard shortcuts
  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  /* ── Data Loading ── */
  const caseIdRef = useRef<number | null>(null);
  const aiRef = useRef<AiData | null>(null);

  const loadData = async (silent = false) => {
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      let caseId = caseIdRef.current;
      if (!caseId) {
        const casesRes = await collectionsApi.listCases({ limit: 1000 });
        const caseEntry = (casesRes.data as CaseInfo[]).find(
          (c) => c.loan_application_id === appId,
        );
        if (!caseEntry) {
          setError('Collection case not found for this application.');
          if (!silent) setLoading(false);
          return;
        }
        caseId = caseEntry.id;
        caseIdRef.current = caseId;
      }
      const fullRes = await collectionsApi.getCaseFull(caseId);
      const fresh = fullRes.data as CaseFullData;

      if (!silent) {
        aiRef.current = fresh.ai;
        setData(fresh);
      } else {
        setData((prev) => ({
          ...fresh,
          ai: aiRef.current ?? prev?.ai ?? fresh.ai,
        }));
      }
    } catch {
      if (!silent) setError('Failed to load case data.');
    }
    if (!silent) setLoading(false);
  };

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appId]);

  /* ── Auto-refresh for new messages (poll every 5s) ── */
  useEffect(() => {
    const interval = setInterval(() => loadData(true), 5000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appId]);

  /* ── Auto-draft WhatsApp message on first open ── */
  useEffect(() => {
    if (
      data?.case?.id &&
      commTab === 'whatsapp' &&
      !draftLoadedRef.current
    ) {
      draftLoadedRef.current = true;
      setDraftLoading(true);
      collectionsApi
        .draftMessage({
          case_id: data.case.id,
          channel: 'whatsapp',
          template_type: 'reminder',
        })
        .then((res) => {
          const msg =
            (res.data as any)?.message ??
            (res.data as any)?.draft ??
            '';
          setWhatsappMsg(msg);
        })
        .catch(() => {})
        .finally(() => setDraftLoading(false));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.case?.id, commTab]);

  /* ── Keyboard Shortcuts ── */
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        target.isContentEditable
      )
        return;

      const d = dataRef.current;
      switch (e.key.toLowerCase()) {
        case 'c':
          if (d?.borrower?.phone)
            window.open(`tel:${d.borrower.phone}`, '_self');
          break;
        case 'w':
          setCommTab('whatsapp');
          break;
        case 'n':
          setCommTab('note');
          break;
        case 'd':
          if (d?.case)
            handleToggleFlagDirect('dispute_active', !d.case.dispute_active, d);
          break;
        case 'e':
          // Escalate — placeholder
          break;
        case '/':
          e.preventDefault();
          break;
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ── Event Handlers ── */

  const handleToggleFlagDirect = async (
    flag: string,
    value: boolean,
    d: CaseFullData,
  ) => {
    try {
      await collectionsApi.updateCase(d.case.id, { [flag]: value });
      await loadData(true);
    } catch {
      /* ignore */
    }
  };

  const handleToggleFlag = async (flag: string, value: boolean) => {
    if (!data?.case) return;
    await handleToggleFlagDirect(flag, value, data);
  };

  const handleSendWhatsApp = async () => {
    if (!whatsappMsg.trim() || !data) return;
    setSending(true);
    try {
      await collectionsApi.sendWhatsApp(data.case.loan_application_id, {
        message: whatsappMsg,
      });
      setWhatsappMsg('');
      await loadData(true);
    } catch {
      /* ignore */
    }
    setSending(false);
  };

  const handleAddNote = async () => {
    if (!noteText.trim() || !data) return;
    setSending(true);
    try {
      await collectionsApi.addRecord(data.case.loan_application_id, {
        channel: 'note',
        notes: noteText,
        action_taken: noteCategory,
        outcome: 'other',
      });
      setNoteText('');
      await loadData(true);
    } catch {
      /* ignore */
    }
    setSending(false);
  };

  const handleCreatePtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!data?.case) return;
    setSending(true);
    try {
      await collectionsApi.createPtp(data.case.id, {
        amount_promised: parseFloat(ptpForm.amount_promised),
        promise_date: ptpForm.promise_date,
        payment_method: ptpForm.payment_method || undefined,
        notes: ptpForm.notes || undefined,
      });
      setShowPtpForm(false);
      setPtpForm({
        amount_promised: '',
        promise_date: '',
        payment_method: '',
        notes: '',
      });
      await loadData(true);
    } catch {
      /* ignore */
    }
    setSending(false);
  };

  const handleOverrideNba = async () => {
    if (!data?.case || !overrideReason.trim()) return;
    try {
      await collectionsApi.overrideNba(data.case.id, {
        action: overrideAction,
        reason: overrideReason,
      });
      setShowOverride(false);
      setOverrideAction('');
      setOverrideReason('');
      await loadData(true);
    } catch {
      /* ignore */
    }
  };

  const handleDraftMessage = async (channel: string) => {
    if (!data?.case?.id) return;
    setDraftLoading(true);
    try {
      const res = await collectionsApi.draftMessage({
        case_id: data.case.id,
        channel,
        template_type: 'reminder',
      });
      const msg =
        (res.data as any)?.message ?? (res.data as any)?.draft ?? '';
      if (channel === 'whatsapp') setWhatsappMsg(msg);
      else if (channel === 'sms') setSmsMsg(msg);
    } catch {
      /* ignore */
    }
    setDraftLoading(false);
  };

  const handleOfferSettlement = async () => {
    if (!data?.case?.id) return;
    try {
      await collectionsApi.createSettlement(data.case.id, {
        auto_calculate: true,
        offer_type: 'full_payment',
        settlement_amount: 1,
      });
      await loadData(true);
    } catch {
      /* ignore */
    }
  };

  /* ── Timeline Computation ── */
  const timeline = useMemo((): TimelineEntry[] => {
    if (!data) return [];
    const entries: TimelineEntry[] = [];

    // Interactions
    data.interactions?.forEach((i) => {
      entries.push({
        id: `int-${i.id}`,
        type: 'interaction',
        subType: i.channel,
        timestamp: i.created_at,
        title: `${i.channel.charAt(0).toUpperCase() + i.channel.slice(1).replace(/_/g, ' ')}${i.outcome ? ' · ' + i.outcome.replace(/_/g, ' ') : ''}`,
        content: i.notes || i.action_taken || '',
        agent: i.agent_name,
      });
    });

    // Chats
    data.chats?.forEach((c) => {
      entries.push({
        id: `chat-${c.id}`,
        type: 'chat',
        subType: c.direction,
        timestamp: c.created_at,
        title: c.direction === 'outbound' ? 'WhatsApp Sent' : 'WhatsApp Received',
        content: c.message,
      });
    });

    // Payments
    data.payments?.forEach((p) => {
      entries.push({
        id: `pay-${p.id}`,
        type: 'payment',
        subType: p.payment_type,
        timestamp: p.payment_date,
        title: `Payment · ${p.status}`,
        content: `${fmtCurrency(p.amount)} via ${p.payment_type.replace(/_/g, ' ')}`,
      });
    });

    // PTPs as system events
    data.ptps?.forEach((p) => {
      entries.push({
        id: `ptp-${p.id}`,
        type: 'system',
        subType: 'ptp',
        timestamp: p.created_at,
        title: `Promise to Pay · ${p.status}`,
        content: `${fmtCurrency(p.amount_promised)} by ${new Date(p.promise_date).toLocaleDateString()}`,
        agent: p.agent_name,
      });
    });

    // Settlements as system events
    data.settlements?.forEach((s) => {
      entries.push({
        id: `sett-${s.id}`,
        type: 'system',
        subType: 'settlement',
        timestamp: s.created_at,
        title: `Settlement · ${s.offer_type.replace(/_/g, ' ')}`,
        content: `${fmtCurrency(s.settlement_amount)} (${s.discount_pct}% off) — ${s.status}`,
      });
    });

    // Sort reverse chronological
    entries.sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
    );

    if (timelineFilter !== 'all') {
      return entries.filter((e) => e.type === timelineFilter);
    }
    return entries;
  }, [data, timelineFilter]);

  /* ═══════════════════════════════════════════════════════════
     Render
     ═══════════════════════════════════════════════════════════ */

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[80vh]">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 text-[var(--color-primary)] animate-spin mx-auto mb-3" />
          <p className="text-[var(--color-text-muted)]">Loading case data…</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center h-[80vh]">
        <div className="text-center">
          <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />
          <p className="text-[var(--color-text)] font-medium mb-1">
            {error || 'Case not found'}
          </p>
          <Link
            to="/backoffice/collections"
            className="text-[var(--color-primary)] hover:underline text-sm"
          >
            &larr; Back to Queue
          </Link>
        </div>
      </div>
    );
  }

  const {
    borrower,
    sector_risk,
    case: caseData,
    loan,
    balance_breakdown,
    payments,
    ptps,
    active_ptp,
    settlements,
    payment_heatmap,
    ai,
  } = data;

  const totalArrears =
    balance_breakdown?.arrears_breakdown?.reduce(
      (sum, a) => sum + a.amount_overdue,
      0,
    ) ?? 0;

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col overflow-hidden">
      {/* ═══════════════════════════════════════════════════════
          TOP BANNER
          ═══════════════════════════════════════════════════════ */}
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl px-5 py-3 flex items-center gap-6 shrink-0">
        {/* ── Left: Borrower Info ── */}
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <Link
            to="/backoffice/collections"
            className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] shrink-0"
          >
            <ArrowLeft size={18} />
          </Link>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-lg font-bold truncate">
                {borrower?.first_name} {borrower?.last_name}
              </h1>
              {loan && (
                <Link
                  to={`/backoffice/review/${loan.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs font-mono text-[var(--color-primary)] hover:underline flex items-center gap-1"
                  title="Open loan details in new tab"
                >
                  #{loan.reference_number}
                  <FileText size={11} />
                </Link>
              )}
            </div>
            <div className="flex items-center gap-3 text-xs text-[var(--color-text-muted)] flex-wrap">
              {borrower?.phone && (
                <a
                  href={`tel:${borrower.phone}`}
                  className="flex items-center gap-1 hover:text-[var(--color-primary)] transition-colors"
                >
                  <Phone size={11} /> {borrower.phone}
                </a>
              )}
              {borrower?.email && (
                <a
                  href={`mailto:${borrower.email}`}
                  className="flex items-center gap-1 hover:text-[var(--color-primary)] transition-colors"
                >
                  <Mail size={11} /> {borrower.email}
                </a>
              )}
              {borrower?.whatsapp_number && (
                <span className="flex items-center gap-1 text-emerald-400">
                  <MessageCircle size={11} /> {borrower.whatsapp_number}
                </span>
              )}
              {borrower?.employer_name && (
                <span className="flex items-center gap-1">
                  <Building size={11} /> {borrower.employer_name}
                </span>
              )}
              {sector_risk && (
                <Badge
                  variant={
                    sector_risk.risk_rating === 'high'
                      ? 'danger'
                      : sector_risk.risk_rating === 'medium'
                        ? 'warning'
                        : 'success'
                  }
                >
                  {sector_risk.sector} · {sector_risk.risk_rating}
                </Badge>
              )}
            </div>
          </div>
        </div>

        {/* ── Center: Key Financials ── */}
        <div className="flex items-center gap-6 shrink-0">
          <div className="text-center">
            <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
              Outstanding
            </div>
            <div className="text-xl font-bold tracking-tight">
              {fmtCurrency(caseData?.total_overdue)}
            </div>
          </div>
          <div className="w-px h-8 bg-[var(--color-border)]" />
          <div className="text-center">
            <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
              Arrears
            </div>
            <div className="text-lg font-semibold text-red-400">
              {fmtCurrency(totalArrears)}
            </div>
          </div>
          <div className="w-px h-8 bg-[var(--color-border)]" />
          <div className="text-center">
            <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
              DPD
            </div>
            <div
              className={`text-xl font-bold ${getDpdColor(caseData?.dpd ?? 0)}`}
            >
              {caseData?.dpd ?? 0}
            </div>
          </div>
          <div className="w-px h-8 bg-[var(--color-border)]" />
          <div className="text-center">
            <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
              Product
            </div>
            <div className="text-sm font-medium capitalize">
              {loan?.purpose || 'Loan'}
            </div>
          </div>
        </div>

        {/* ── Right: Flags + Last Contact ── */}
        <div className="flex items-center gap-2 shrink-0">
          {caseData?.dispute_active && (
            <Badge variant="purple">Dispute</Badge>
          )}
          {caseData?.vulnerability_flag && (
            <Badge variant="warning">Vulnerable</Badge>
          )}
          {caseData?.do_not_contact && (
            <Badge variant="danger">DNC</Badge>
          )}
          {caseData?.hardship_flag && (
            <Badge variant="info">Hardship</Badge>
          )}
          <div className="text-xs text-[var(--color-text-muted)] ml-1 whitespace-nowrap">
            {caseData?.last_contact_at
              ? timeAgo(caseData.last_contact_at)
              : 'No contact'}
          </div>
          <button
            onClick={() => loadData(true)}
            className="p-1.5 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-colors"
            title="Refresh"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════
          3-PANEL LAYOUT
          ═══════════════════════════════════════════════════════ */}
      <div className="flex-1 flex overflow-hidden gap-4 mt-4 min-h-0">
        {/* ═══════════════════════════════════════════
            LEFT PANEL — AI Command Center (~30%)
            ═══════════════════════════════════════════ */}
        <div className="w-[30%] min-w-[280px] overflow-y-auto space-y-3 pr-1 pb-4">
          {/* ── AI Recommendation Card ── */}
          <Card
            padding="sm"
            className={`border-l-4 ${getUrgencyBorder(ai?.nba?.timing)}`}
          >
            <div className="flex items-center gap-2 mb-3">
              <div className="p-1.5 rounded-lg bg-[var(--color-primary)]/15">
                <Brain size={14} className="text-[var(--color-primary)]" />
              </div>
              <span className="font-semibold text-sm">AI Recommendation</span>
              {ai?.nba?.confidence_label && (
                <Badge
                  variant={getConfidenceVariant(ai.nba.confidence_label)}
                  className="ml-auto"
                >
                  {ai.nba.confidence_label}{' '}
                  {Math.round((ai.nba.confidence ?? 0) * 100)}%
                </Badge>
              )}
            </div>

            <div className="space-y-3">
              {/* Action + Timing */}
              <div>
                <div className="text-base font-semibold capitalize text-[var(--color-primary)]">
                  {ai?.nba?.action?.replace(/_/g, ' ') || 'No recommendation'}
                </div>
                <div className="text-xs text-[var(--color-text-muted)] mt-0.5 flex items-center gap-2 flex-wrap">
                  <span className="flex items-center gap-1">
                    <Clock size={10} /> {ai?.nba?.timing || '—'}
                  </span>
                  <span>·</span>
                  <span className="capitalize">
                    {ai?.nba?.best_channel?.replace(/_/g, ' ') || '—'}
                  </span>
                  {ai?.nba?.best_number && (
                    <>
                      <span>·</span>
                      <span className="font-mono">{ai.nba.best_number}</span>
                    </>
                  )}
                </div>
              </div>

              {/* Suggested Offer */}
              {ai?.nba?.suggested_offer && (
                <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                  <div className="text-[10px] uppercase tracking-wider text-emerald-400 font-semibold mb-0.5">
                    Suggested Offer
                  </div>
                  {typeof ai.nba.suggested_offer === 'string' ? (
                    <p className="text-sm text-[var(--color-text)]">{ai.nba.suggested_offer}</p>
                  ) : (
                    (() => {
                      const offer = ai.nba.suggested_offer as NbaSuggestedOffer;
                      return (
                        <div className="text-sm text-[var(--color-text)] space-y-0.5">
                          <p className="font-medium capitalize">
                            {(offer.offer_type || '').replace(/_/g, ' ')}
                          </p>
                          {offer.settlement_amount != null && (
                            <p>Amount: <span className="font-semibold">${Number(offer.settlement_amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                              {offer.discount_pct != null && offer.discount_pct > 0 && (
                                <span className="text-emerald-400 ml-1">({offer.discount_pct}% discount)</span>
                              )}
                            </p>
                          )}
                          {offer.plan_months != null && offer.plan_months > 0 && (
                            <p>{offer.plan_months}-month plan at ${Number(offer.plan_monthly_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}/mo</p>
                          )}
                          {offer.lump_sum != null && offer.lump_sum > 0 && (
                            <p>Lump sum: ${Number(offer.lump_sum).toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
                          )}
                        </div>
                      );
                    })()
                  )}
                </div>
              )}

              {/* Reasoning */}
              {ai?.nba?.reasoning && (
                <p className="text-sm text-[var(--color-text-muted)] leading-relaxed">
                  {ai.nba.reasoning}
                </p>
              )}

              {/* Tone Guidance */}
              {ai?.nba?.tone_guidance && (
                <div className="text-xs text-[var(--color-text-muted)] italic border-t border-[var(--color-border)] pt-2">
                  <span className="font-medium not-italic">Tone:</span>{' '}
                  {ai.nba.tone_guidance}
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex items-center gap-2 pt-1">
                <Button
                  size="sm"
                  onClick={() => {
                    if (ai?.nba?.best_channel === 'whatsapp') {
                      setCommTab('whatsapp');
                    } else if (ai?.nba?.best_channel === 'phone' && borrower?.phone) {
                      window.open(`tel:${borrower.phone}`, '_self');
                    } else if (ai?.nba?.best_channel === 'email' && borrower?.email) {
                      window.open(`mailto:${borrower.email}`);
                    } else {
                      setCommTab('whatsapp');
                    }
                  }}
                >
                  {ai?.nba?.best_channel === 'phone' ? (
                    <Phone size={14} className="mr-1.5" />
                  ) : ai?.nba?.best_channel === 'email' ? (
                    <Mail size={14} className="mr-1.5" />
                  ) : (
                    <MessageCircle size={14} className="mr-1.5" />
                  )}
                  {getNbaActionLabel(ai?.nba?.action)}
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    setCommTab('whatsapp');
                    handleDraftMessage('whatsapp');
                  }}
                  title="Send WhatsApp"
                >
                  <MessageCircle size={14} />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setShowOverride(true);
                    setOverrideAction(ai?.nba?.action || '');
                  }}
                  title="Override recommendation"
                >
                  <Edit size={14} />
                </Button>
              </div>
            </div>
          </Card>

          {/* ── Propensity to Pay Gauge ── */}
          {ai?.propensity != null && (
            <Card padding="sm">
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-sm flex items-center gap-2">
                  <Target size={14} className="text-[var(--color-primary)]" />
                  Propensity to Pay
                </span>
                <span
                  className={`text-xl font-bold ${getPropensityColor(ai.propensity.score ?? 0)}`}
                >
                  {Math.round(ai.propensity.score ?? 0)}
                </span>
              </div>

              {/* Gauge bar */}
              <div className="w-full h-2.5 bg-[var(--color-bg)] rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${getPropensityBarColor(ai.propensity.score ?? 0)}`}
                  style={{ width: `${Math.min(ai.propensity.score ?? 0, 100)}%` }}
                />
              </div>

              {/* Trend */}
              <div className="flex items-center gap-1.5 mt-1.5 text-xs text-[var(--color-text-muted)]">
                <span>Trend:</span>
                {ai.propensity.trend === 'up' && (
                  <TrendingUp size={12} className="text-emerald-400" />
                )}
                {ai.propensity.trend === 'down' && (
                  <TrendingDown size={12} className="text-red-400" />
                )}
                {ai.propensity.trend !== 'up' &&
                  ai.propensity.trend !== 'down' && <span>→</span>}
                <span className="capitalize">{ai.propensity.trend}</span>
              </div>

              {/* Factors */}
              {(ai.propensity.factors_positive?.length > 0 ||
                ai.propensity.factors_negative?.length > 0) && (
                <div className="mt-3 space-y-1 border-t border-[var(--color-border)] pt-2">
                  {ai.propensity.factors_positive?.slice(0, 3).map((f, i) => (
                    <div
                      key={`pos-${i}`}
                      className="text-xs flex items-start gap-1.5 text-emerald-400"
                    >
                      <CheckCircle size={10} className="mt-0.5 shrink-0" />
                      <span>{f}</span>
                    </div>
                  ))}
                  {ai.propensity.factors_negative?.slice(0, 3).map((f, i) => (
                    <div
                      key={`neg-${i}`}
                      className="text-xs flex items-start gap-1.5 text-red-400"
                    >
                      <XCircle size={10} className="mt-0.5 shrink-0" />
                      <span>{f}</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}

          {/* ── Behavioral Patterns ── */}
          {ai?.patterns?.length > 0 && (
            <Card padding="sm">
              <h3 className="font-semibold text-sm mb-2.5 flex items-center gap-2">
                <Activity size={14} className="text-[var(--color-primary)]" />
                Behavioral Patterns
              </h3>
              <div className="space-y-1.5">
                {ai.patterns.map((p, i) => (
                  <div
                    key={i}
                    className="p-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]"
                  >
                    <span className="text-[10px] uppercase tracking-wider font-semibold text-[var(--color-primary)]">
                      {p.category}
                    </span>
                    <p className="text-xs text-[var(--color-text-muted)] mt-0.5 leading-relaxed">
                      {p.insight}
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* ── Risk Signals ── */}
          {ai?.risk_signals?.length > 0 && (
            <Card padding="sm">
              <h3 className="font-semibold text-sm mb-2.5 flex items-center gap-2">
                <AlertTriangle size={14} className="text-amber-400" />
                Risk Signals
              </h3>
              <div className="space-y-1.5">
                {ai.risk_signals.map((r, i) => (
                  <div
                    key={i}
                    className={`flex items-start gap-2 p-2 rounded-lg border ${
                      r.severity === 'high'
                        ? 'bg-red-500/10 border-red-500/20'
                        : r.severity === 'medium'
                          ? 'bg-amber-500/10 border-amber-500/20'
                          : 'bg-sky-500/10 border-sky-500/20'
                    }`}
                  >
                    <AlertCircle
                      size={12}
                      className={`mt-0.5 shrink-0 ${
                        r.severity === 'high'
                          ? 'text-red-400'
                          : r.severity === 'medium'
                            ? 'text-amber-400'
                            : 'text-sky-400'
                      }`}
                    />
                    <div>
                      <span className="text-xs font-medium">{r.category}</span>
                      <p className="text-xs text-[var(--color-text-muted)]">
                        {r.signal}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* ── Similar Borrower Outcomes ── */}
          {ai?.similar_outcomes && (
            <Card padding="sm">
              <h3 className="font-semibold text-sm mb-2.5 flex items-center gap-2">
                <BarChart3 size={14} className="text-[var(--color-primary)]" />
                Similar Outcomes
              </h3>
              <div className="grid grid-cols-2 gap-3 text-center">
                <div className="p-2 rounded-lg bg-[var(--color-bg)]">
                  <div className="text-2xl font-bold text-emerald-400">
                    {Math.round(
                      (ai.similar_outcomes.cure_rate ?? 0) * 100,
                    )}
                    %
                  </div>
                  <div className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wider">
                    Cure Rate
                  </div>
                </div>
                <div className="p-2 rounded-lg bg-[var(--color-bg)]">
                  <div className="text-2xl font-bold">
                    {ai.similar_outcomes.avg_resolution_days ?? 0}
                  </div>
                  <div className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wider">
                    Avg Days
                  </div>
                </div>
              </div>
              {ai.similar_outcomes.description && (
                <p className="text-xs text-[var(--color-text-muted)] mt-2 leading-relaxed">
                  {ai.similar_outcomes.description}
                </p>
              )}
              <div className="text-[10px] text-[var(--color-text-muted)] mt-1">
                Based on {ai.similar_outcomes.total_similar ?? 0} cases (
                {ai.similar_outcomes.dpd_band})
              </div>
            </Card>
          )}
        </div>

        {/* ═══════════════════════════════════════════
            CENTER PANEL — Timeline + Communication (~40%)
            ═══════════════════════════════════════════ */}
        <div className="w-[40%] min-w-[340px] flex flex-col overflow-hidden">
          {/* ── Filter Bar ── */}
          <div className="flex items-center gap-1 mb-3 shrink-0 flex-wrap">
            {(
              [
                { key: 'all', label: 'All' },
                { key: 'interaction', label: 'Calls' },
                { key: 'chat', label: 'Messages' },
                { key: 'payment', label: 'Payments' },
                { key: 'system', label: 'System' },
              ] as const
            ).map((f) => (
              <button
                key={f.key}
                onClick={() => setTimelineFilter(f.key)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                  timelineFilter === f.key
                    ? 'bg-[var(--color-primary)] text-white'
                    : 'bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] border border-[var(--color-border)]'
                }`}
              >
                {f.label}
              </button>
            ))}
            <span className="text-xs text-[var(--color-text-muted)] ml-auto tabular-nums">
              {timeline.length} events
            </span>
          </div>

          {/* ── Timeline ── */}
          <div
            ref={timelineRef}
            className="flex-1 overflow-y-auto space-y-1.5 min-h-0 pb-2"
          >
            {timeline.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-[var(--color-text-muted)]">
                <Activity size={32} className="mb-2 opacity-30" />
                <p className="text-sm">No events to display</p>
              </div>
            )}
            {timeline.map((entry) => (
              <div
                key={entry.id}
                className="flex gap-3 p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-[var(--color-primary)]/30 transition-colors group"
              >
                <div
                  className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${getTimelineIconBg(entry.type, entry.subType)}`}
                >
                  {getTimelineIcon(entry.type, entry.subType)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium truncate">
                      {entry.title}
                    </span>
                    {entry.agent && (
                      <span className="text-[10px] text-[var(--color-text-muted)]">
                        by {entry.agent}
                      </span>
                    )}
                  </div>
                  {entry.content && (
                    <p className="text-xs text-[var(--color-text-muted)] mt-0.5 line-clamp-2 leading-relaxed">
                      {entry.content}
                    </p>
                  )}
                </div>
                <div className="text-[10px] text-[var(--color-text-muted)] shrink-0 whitespace-nowrap pt-0.5 tabular-nums">
                  {fmtShortDate(entry.timestamp)}
                </div>
              </div>
            ))}
          </div>

          {/* ── Communication Compose Area ── */}
          <div className="border-t border-[var(--color-border)] pt-3 mt-2 shrink-0">
            {/* Tabs */}
            <div className="flex gap-1 mb-2">
              {(
                [
                  { key: 'whatsapp' as const, label: 'WhatsApp', icon: MessageCircle },
                  { key: 'sms' as const, label: 'SMS', icon: MessageSquare },
                  { key: 'note' as const, label: 'Note', icon: FileText },
                ] as Array<{ key: 'whatsapp' | 'sms' | 'note'; label: string; icon: LucideIcon }>
              ).map((t) => (
                <button
                  key={t.key}
                  onClick={() => setCommTab(t.key)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    commTab === t.key
                      ? 'bg-[var(--color-primary)] text-white'
                      : 'text-[var(--color-text-muted)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text)]'
                  }`}
                >
                  <t.icon size={12} /> {t.label}
                </button>
              ))}
            </div>

            {/* WhatsApp Compose */}
            {commTab === 'whatsapp' && (
              <div className="flex gap-2">
                <textarea
                  value={whatsappMsg}
                  onChange={(e) => setWhatsappMsg(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && e.metaKey) handleSendWhatsApp();
                  }}
                  placeholder={
                    draftLoading
                      ? 'AI is drafting a message…'
                      : 'Type WhatsApp message…'
                  }
                  className={`${inputCls} flex-1 resize-none`}
                  rows={2}
                  disabled={draftLoading}
                />
                <div className="flex flex-col gap-1">
                  <Button
                    size="sm"
                    onClick={handleSendWhatsApp}
                    disabled={sending || !whatsappMsg.trim()}
                    title="Send (⌘+Enter)"
                  >
                    <Send size={14} />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDraftMessage('whatsapp')}
                    disabled={draftLoading}
                    title="AI Draft"
                  >
                    <Sparkles size={14} />
                  </Button>
                </div>
              </div>
            )}

            {/* SMS Compose */}
            {commTab === 'sms' && (
              <div className="flex gap-2">
                <textarea
                  value={smsMsg}
                  onChange={(e) => setSmsMsg(e.target.value)}
                  placeholder="Type SMS message…"
                  className={`${inputCls} flex-1 resize-none`}
                  rows={2}
                />
                <div className="flex flex-col gap-1">
                  <Button
                    size="sm"
                    onClick={() => {
                      /* SMS send – placeholder */
                    }}
                    disabled={!smsMsg.trim()}
                  >
                    <Send size={14} />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDraftMessage('sms')}
                    disabled={draftLoading}
                    title="AI Draft"
                  >
                    <Sparkles size={14} />
                  </Button>
                </div>
              </div>
            )}

            {/* Note Compose */}
            {commTab === 'note' && (
              <div className="space-y-2">
                <select
                  value={noteCategory}
                  onChange={(e) => setNoteCategory(e.target.value)}
                  className={inputSmCls}
                >
                  <option value="general">General Note</option>
                  <option value="call_attempt">Call Attempt</option>
                  <option value="promise_follow_up">Promise Follow-up</option>
                  <option value="escalation">Escalation</option>
                  <option value="hardship_review">Hardship Review</option>
                </select>
                <div className="flex gap-2">
                  <textarea
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && e.metaKey) handleAddNote();
                    }}
                    placeholder="Add case note…"
                    className={`${inputCls} flex-1 resize-none`}
                    rows={2}
                  />
                  <Button
                    size="sm"
                    onClick={handleAddNote}
                    disabled={sending || !noteText.trim()}
                    title="Save (⌘+Enter)"
                  >
                    <Plus size={14} />
                  </Button>
                </div>
              </div>
            )}

            {/* Keyboard hints */}
            <div className="flex gap-3 mt-2 text-[10px] text-[var(--color-text-muted)]">
              {[
                { key: 'C', label: 'Call' },
                { key: 'W', label: 'WhatsApp' },
                { key: 'N', label: 'Note' },
                { key: 'D', label: 'Dispute' },
                { key: 'E', label: 'Escalate' },
              ].map((s) => (
                <span key={s.key} className="flex items-center gap-1">
                  <kbd className="px-1 py-0.5 rounded bg-[var(--color-bg)] border border-[var(--color-border)] font-mono">
                    {s.key}
                  </kbd>
                  {s.label}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* ═══════════════════════════════════════════
            RIGHT PANEL — Account Details + Tools (~30%)
            ═══════════════════════════════════════════ */}
        <div className="w-[30%] min-w-[280px] overflow-y-auto space-y-3 pl-1 pb-4">
          {/* ── Loan Details ── */}
          <Card padding="sm">
            <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
              <CreditCard size={14} className="text-[var(--color-primary)]" />
              Loan Details
            </h3>
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
                  Amount
                </div>
                <div className="font-medium">
                  {fmtCurrency(loan?.amount_approved)}
                </div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
                  Rate
                </div>
                <div className="font-medium">{loan?.interest_rate}%</div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
                  Term
                </div>
                <div className="font-medium">{loan?.term_months} months</div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
                  Monthly PMT
                </div>
                <div className="font-medium">
                  {fmtCurrency(loan?.monthly_payment)}
                </div>
              </div>
              <div className="col-span-2">
                <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
                  Purpose
                </div>
                <div className="font-medium capitalize">{loan?.purpose}</div>
              </div>
              {loan?.disbursed_at && (
                <div className="col-span-2">
                  <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
                    Disbursed
                  </div>
                  <div className="font-medium">
                    {new Date(loan.disbursed_at).toLocaleDateString()}
                  </div>
                </div>
              )}
            </div>
          </Card>

          {/* ── Balance Breakdown ── */}
          <Card padding="sm">
            <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
              <DollarSign size={14} className="text-[var(--color-primary)]" />
              Balance Breakdown
            </h3>
            <div className="space-y-1.5">
              {[
                {
                  label: 'Principal',
                  value: balance_breakdown?.total_principal,
                },
                {
                  label: 'Interest',
                  value: balance_breakdown?.total_interest,
                },
                { label: 'Fees', value: balance_breakdown?.total_fees },
              ].map((row) => (
                <div
                  key={row.label}
                  className="flex justify-between text-sm"
                >
                  <span className="text-[var(--color-text-muted)]">
                    {row.label}
                  </span>
                  <span className="tabular-nums">{fmtCurrency(row.value)}</span>
                </div>
              ))}
              <div className="border-t border-[var(--color-border)] pt-1.5 flex justify-between text-sm font-semibold">
                <span>Total</span>
                <span className="tabular-nums">
                  {fmtCurrency(
                    (balance_breakdown?.total_principal ?? 0) +
                      (balance_breakdown?.total_interest ?? 0) +
                      (balance_breakdown?.total_fees ?? 0),
                  )}
                </span>
              </div>
            </div>

            {/* Arrears by installment */}
            {balance_breakdown?.arrears_breakdown?.length > 0 && (
              <div className="mt-3 border-t border-[var(--color-border)] pt-2.5">
                <div className="text-[10px] uppercase tracking-wider font-semibold text-red-400 mb-1.5">
                  Arrears by Installment
                </div>
                <div className="space-y-1 max-h-[100px] overflow-y-auto">
                  {balance_breakdown.arrears_breakdown.map((a, i) => (
                    <div
                      key={i}
                      className="flex justify-between text-xs"
                    >
                      <span className="text-[var(--color-text-muted)]">
                        #{a.installment} ·{' '}
                        {new Date(a.due_date).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                        })}
                      </span>
                      <span className="text-red-400 font-medium tabular-nums">
                        {fmtCurrency(a.amount_overdue)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>

          {/* ── Recent Payments (last 6) ── */}
          <Card padding="sm">
            <h3 className="font-semibold text-sm mb-2.5 flex items-center gap-2">
              <Activity size={14} className="text-[var(--color-primary)]" />
              Recent Payments
            </h3>
            {payments?.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                      <th className="text-left py-1 font-medium">Date</th>
                      <th className="text-right py-1 font-medium">Amount</th>
                      <th className="text-right py-1 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payments.slice(0, 6).map((p) => (
                      <tr
                        key={p.id}
                        className="border-b border-[var(--color-border)]/30"
                      >
                        <td className="py-1.5 text-[var(--color-text-muted)]">
                          {new Date(p.payment_date).toLocaleDateString(
                            'en-US',
                            { month: 'short', day: 'numeric' },
                          )}
                        </td>
                        <td className="text-right font-medium tabular-nums">
                          {fmtCurrency(p.amount)}
                        </td>
                        <td className="text-right">
                          <Badge
                            variant={
                              p.status === 'completed'
                                ? 'success'
                                : p.status === 'pending'
                                  ? 'warning'
                                  : 'info'
                            }
                          >
                            {p.status}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-[var(--color-text-muted)]">
                No payments recorded
              </p>
            )}
          </Card>

          {/* ── 12-Month Payment Heatmap ── */}
          {payment_heatmap?.length > 0 && (
            <Card padding="sm">
              <h3 className="font-semibold text-sm mb-2.5 flex items-center gap-2">
                <Calendar size={14} className="text-[var(--color-primary)]" />
                Payment Heatmap
              </h3>
              <div className="grid grid-cols-6 gap-1.5">
                {payment_heatmap.slice(-12).map((h, i) => (
                  <div
                    key={i}
                    className={`aspect-square rounded-md flex items-center justify-center text-[9px] font-bold ${getHeatmapColor(h.status)}`}
                    title={`${h.month}: ${h.status.replace(/_/g, ' ')}`}
                  >
                    {h.month?.slice(5, 7) || ''}
                  </div>
                ))}
              </div>
              <div className="flex gap-3 mt-2 text-[9px] text-[var(--color-text-muted)]">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-sm bg-emerald-500" /> On Time
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-sm bg-amber-500" /> Late
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-sm bg-red-500" /> Missed
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-sm bg-gray-600" /> None
                </span>
              </div>
            </Card>
          )}

          {/* ── PTP Manager ── */}
          <Card padding="sm">
            <div className="flex items-center justify-between mb-2.5">
              <h3 className="font-semibold text-sm flex items-center gap-2">
                <Handshake size={14} className="text-[var(--color-primary)]" />
                Promises to Pay
              </h3>
              <button
                onClick={() => setShowPtpForm(!showPtpForm)}
                className="text-xs text-[var(--color-primary)] hover:underline flex items-center gap-1"
              >
                <Plus size={12} /> New
              </button>
            </div>

            {/* Active PTP highlight */}
            {active_ptp && (
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 mb-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-amber-400">
                    Active Promise
                  </span>
                  <Badge variant="warning">{active_ptp.status}</Badge>
                </div>
                <div className="text-lg font-bold mt-1">
                  {fmtCurrency(active_ptp.amount_promised)}
                </div>
                <div className="text-xs text-[var(--color-text-muted)] mt-0.5">
                  Due:{' '}
                  {new Date(active_ptp.promise_date).toLocaleDateString()}
                  {active_ptp.payment_method &&
                    ` · ${active_ptp.payment_method.replace(/_/g, ' ')}`}
                </div>
              </div>
            )}

            {/* PTP Create Form */}
            {showPtpForm && (
              <form
                onSubmit={handleCreatePtp}
                className="space-y-2 mb-2.5 p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]"
              >
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="number"
                    required
                    min="0.01"
                    step="0.01"
                    placeholder="Amount"
                    value={ptpForm.amount_promised}
                    onChange={(e) =>
                      setPtpForm((f) => ({
                        ...f,
                        amount_promised: e.target.value,
                      }))
                    }
                    className={inputSmCls}
                  />
                  <input
                    type="date"
                    required
                    value={ptpForm.promise_date}
                    onChange={(e) =>
                      setPtpForm((f) => ({
                        ...f,
                        promise_date: e.target.value,
                      }))
                    }
                    className={inputSmCls}
                  />
                </div>
                <select
                  value={ptpForm.payment_method}
                  onChange={(e) =>
                    setPtpForm((f) => ({
                      ...f,
                      payment_method: e.target.value,
                    }))
                  }
                  className={inputSmCls}
                >
                  <option value="">Payment method…</option>
                  <option value="bank_transfer">Bank Transfer</option>
                  <option value="online">Online</option>
                  <option value="cash">Cash</option>
                  <option value="mobile_money">Mobile Money</option>
                </select>
                <input
                  type="text"
                  placeholder="Notes (optional)"
                  value={ptpForm.notes}
                  onChange={(e) =>
                    setPtpForm((f) => ({ ...f, notes: e.target.value }))
                  }
                  className={inputSmCls}
                />
                <div className="flex gap-2">
                  <Button size="sm" type="submit" disabled={sending}>
                    Create
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    type="button"
                    onClick={() => setShowPtpForm(false)}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            )}

            {/* PTP History */}
            <div className="space-y-1.5 max-h-[140px] overflow-y-auto">
              {ptps?.slice(0, 5).map((p) => (
                <div
                  key={p.id}
                  className="flex items-center justify-between text-xs p-2 rounded-lg bg-[var(--color-bg)]"
                >
                  <div>
                    <span className="font-medium tabular-nums">
                      {fmtCurrency(p.amount_promised)}
                    </span>
                    <span className="text-[var(--color-text-muted)] ml-2">
                      {new Date(p.promise_date).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                      })}
                    </span>
                  </div>
                  <Badge
                    variant={
                      p.status === 'kept'
                        ? 'success'
                        : p.status === 'broken'
                          ? 'danger'
                          : p.status === 'pending'
                            ? 'warning'
                            : 'info'
                    }
                  >
                    {p.status}
                  </Badge>
                </div>
              ))}
              {(!ptps || ptps.length === 0) && !active_ptp && (
                <p className="text-xs text-[var(--color-text-muted)] py-2">
                  No promises recorded
                </p>
              )}
            </div>
          </Card>

          {/* ── Quick Actions ── */}
          <Card padding="sm">
            <h3 className="font-semibold text-sm mb-2.5 flex items-center gap-2">
              <Zap size={14} className="text-amber-400" />
              Quick Actions
            </h3>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() =>
                  handleToggleFlag(
                    'dispute_active',
                    !caseData?.dispute_active,
                  )
                }
                className={`p-2.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all ${
                  caseData?.dispute_active
                    ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                    : 'bg-[var(--color-bg)] text-[var(--color-text-muted)] border border-[var(--color-border)] hover:border-purple-500/30 hover:text-purple-400'
                }`}
              >
                <Flag size={12} />
                {caseData?.dispute_active ? 'Remove Dispute' : 'Flag Dispute'}
              </button>
              <button
                onClick={() =>
                  handleToggleFlag(
                    'vulnerability_flag',
                    !caseData?.vulnerability_flag,
                  )
                }
                className={`p-2.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all ${
                  caseData?.vulnerability_flag
                    ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                    : 'bg-[var(--color-bg)] text-[var(--color-text-muted)] border border-[var(--color-border)] hover:border-amber-500/30 hover:text-amber-400'
                }`}
              >
                <ShieldAlert size={12} />
                Vulnerability
              </button>
              <button
                onClick={() => {
                  /* Escalation logic – placeholder */
                }}
                className="p-2.5 rounded-lg text-xs font-medium flex items-center gap-1.5 bg-[var(--color-bg)] text-[var(--color-text-muted)] border border-[var(--color-border)] hover:border-red-500/30 hover:text-red-400 transition-all"
              >
                <AlertTriangle size={12} />
                Escalate
              </button>
              <button
                onClick={handleOfferSettlement}
                className="p-2.5 rounded-lg text-xs font-medium flex items-center gap-1.5 bg-[var(--color-bg)] text-[var(--color-text-muted)] border border-[var(--color-border)] hover:border-emerald-500/30 hover:text-emerald-400 transition-all"
              >
                <DollarSign size={12} />
                Offer Plan
              </button>
            </div>
          </Card>

          {/* ── Settlement Offers ── */}
          {settlements?.length > 0 && (
            <Card padding="sm">
              <h3 className="font-semibold text-sm mb-2.5 flex items-center gap-2">
                <FileText size={14} className="text-[var(--color-primary)]" />
                Settlement Offers
              </h3>
              <div className="space-y-1.5">
                {settlements.slice(0, 3).map((s) => (
                  <div
                    key={s.id}
                    className="p-2.5 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium capitalize">
                        {s.offer_type.replace(/_/g, ' ')}
                      </span>
                      <Badge
                        variant={
                          s.status === 'accepted'
                            ? 'success'
                            : s.status === 'rejected' || s.status === 'expired'
                              ? 'danger'
                              : 'warning'
                        }
                      >
                        {s.status}
                      </Badge>
                    </div>
                    <div className="flex items-baseline gap-2 mt-1">
                      <span className="text-sm font-semibold text-emerald-400 tabular-nums">
                        {fmtCurrency(s.settlement_amount)}
                      </span>
                      {s.discount_pct > 0 && (
                        <span className="text-[10px] text-[var(--color-text-muted)]">
                          ({s.discount_pct}% off)
                        </span>
                      )}
                    </div>
                    {s.plan_months && (
                      <div className="text-xs text-[var(--color-text-muted)] mt-0.5">
                        {s.plan_months}mo × {fmtCurrency(s.plan_monthly_amount)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════
          OVERRIDE NBA MODAL
          ═══════════════════════════════════════════════════════ */}
      {showOverride && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
          onClick={() => setShowOverride(false)}
        >
          <div
            className="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] p-6 w-[420px] shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-base flex items-center gap-2">
                <Edit size={16} className="text-[var(--color-primary)]" />
                Override NBA
              </h3>
              <button
                onClick={() => setShowOverride(false)}
                className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
              >
                <X size={16} />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1.5 font-medium">
                  New Action
                </label>
                <select
                  value={overrideAction}
                  onChange={(e) => setOverrideAction(e.target.value)}
                  className={inputCls}
                >
                  <option value="">Select action…</option>
                  <option value="call">Call</option>
                  <option value="send_whatsapp">Send WhatsApp</option>
                  <option value="send_sms">Send SMS</option>
                  <option value="send_email">Send Email</option>
                  <option value="offer_settlement">Offer Settlement</option>
                  <option value="escalate">Escalate</option>
                  <option value="skip">Skip / No Action</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1.5 font-medium">
                  Reason <span className="text-red-400">*</span>
                </label>
                <textarea
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  placeholder="Why are you overriding the AI recommendation?"
                  className={`${inputCls} resize-none`}
                  rows={3}
                />
              </div>
              <div className="flex justify-end gap-2 pt-1">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setShowOverride(false)}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  onClick={handleOverrideNba}
                  disabled={!overrideReason.trim()}
                >
                  Override
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
