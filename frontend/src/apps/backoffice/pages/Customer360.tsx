import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, RefreshCw, Sparkles, TrendingUp, TrendingDown,
  AlertTriangle, CheckCircle, Clock, CreditCard, FileText,
  MessageCircle, Shield, Send, ChevronDown, Plus, X,
  Banknote, User, Phone, Mail, Building, Calendar,
  Activity, Bot, StickyNote, FileUp, Eye, EyeOff,
  Download, ExternalLink, Scroll, Edit3, Save, XCircle,
} from 'lucide-react';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, LineChart, Line, CartesianGrid, Legend,
} from 'recharts';
import Card from '../../../components/ui/Card';
import Badge, { getStatusBadge } from '../../../components/ui/Badge';
import Button from '../../../components/ui/Button';
import { customerApi, underwriterApi, loanApi, conversationsApi } from '../../../api/endpoints';

// ── Types ────────────────────────────────────────────────────────────────
interface QuickStats {
  total_lifetime_value: number;
  active_products: number;
  total_outstanding: number;
  worst_dpd: number;
  payment_success_rate: number;
  relationship_length_days: number;
  last_contact: string | null;
  last_contact_channel: string | null;
  last_contact_direction: string | null;
}

interface AISummary {
  summary_text: string;
  sentiment: string;
  highlights: string[];
  risk_narrative: string;
  recommendations: Array<{ text: string; priority: string; category: string }>;
  confidence_score: number;
}

interface TimelineEvent {
  timestamp: string;
  category: string;
  icon_type: string;
  title: string;
  description: string;
  actor: string;
  entity_type: string;
  entity_id: number;
}

interface AskAIMsg {
  role: 'user' | 'assistant';
  content: string;
}

// ── Helper fns ───────────────────────────────────────────────────────────
function fmtDate(d: string | null) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}
function fmtDateTime(d: string | null) {
  if (!d) return '—';
  return new Date(d).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}
function fmtMoney(v: number | null | undefined) {
  if (v == null) return '—';
  return `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
function maskId(id: string | null) {
  if (!id || id.length < 4) return id || '—';
  return '****' + id.slice(-4);
}

/** Trigger a browser download from a blob response */
async function downloadBlob(promise: Promise<any>, fallbackName: string) {
  try {
    const res = await promise;
    const blob = res.data instanceof Blob ? res.data : new Blob([res.data]);
    const cd = res.headers?.['content-disposition'] || '';
    const match = cd.match(/filename="?([^";\n]+)"?/);
    const name = match?.[1] || fallbackName;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    console.error('Download failed', e);
    alert('Download failed. The file may not be available.');
  }
}

const SENTIMENT_COLORS: Record<string, string> = {
  positive: 'text-emerald-400',
  neutral: 'text-sky-400',
  concerning: 'text-amber-400',
  critical: 'text-red-400',
};
const SENTIMENT_BG: Record<string, string> = {
  positive: 'bg-emerald-500/15',
  neutral: 'bg-sky-500/15',
  concerning: 'bg-amber-500/15',
  critical: 'bg-red-500/15',
};
const PRIORITY_COLORS: Record<string, string> = {
  high: 'text-red-400',
  medium: 'text-amber-400',
  low: 'text-sky-400',
};

const TABS = [
  'Overview', 'Applications', 'Loans', 'Payments',
  'Collections', 'Communications', 'Documents', 'Bureau Alerts', 'Audit Trail',
] as const;
type TabName = typeof TABS[number];

const PIE_COLORS = ['#38bdf8', '#818cf8', '#34d399', '#fb923c', '#f87171', '#a78bfa'];

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  application: <FileText className="w-4 h-4" />,
  loan: <Banknote className="w-4 h-4" />,
  payment: <CreditCard className="w-4 h-4" />,
  collection: <Phone className="w-4 h-4" />,
  communication: <MessageCircle className="w-4 h-4" />,
  document: <FileUp className="w-4 h-4" />,
  system: <Shield className="w-4 h-4" />,
};

// ── Main Component ───────────────────────────────────────────────────────
export default function Customer360() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const targetId = Number(id);

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabName>('Overview');

  // AI
  const [aiSummary, setAiSummary] = useState<AISummary | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [showAskAI, setShowAskAI] = useState(false);
  const [askQuestion, setAskQuestion] = useState('');
  const [askHistory, setAskHistory] = useState<AskAIMsg[]>([]);
  const [askLoading, setAskLoading] = useState(false);

  // Timeline
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [tlLoading, setTlLoading] = useState(false);
  const [tlFilter, setTlFilter] = useState<string[]>([]);
  const [tlSearch, setTlSearch] = useState('');

  // ID reveal
  const [idRevealed, setIdRevealed] = useState(false);

  // New Communication
  const [showNewComm, setShowNewComm] = useState(false);
  const [commChannel, setCommChannel] = useState<'web' | 'whatsapp'>('web');
  const [commMessage, setCommMessage] = useState('');
  const [commSending, setCommSending] = useState(false);

  // Active conversation (inline chat from Communications tab)
  const [activeConvId, setActiveConvId] = useState<number | null>(null);
  const [activeConvMessages, setActiveConvMessages] = useState<Array<{ id: number; role: string; content: string; created_at: string }>>([]);
  const [inlineMsg, setInlineMsg] = useState('');
  const [inlineSending, setInlineSending] = useState(false);

  // ── Loaders ──
  const load360 = useCallback(async () => {
    setLoading(true);
    try {
      const res = await customerApi.get360(targetId);
      setData(res.data);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [targetId]);

  const loadAiSummary = useCallback(async () => {
    setAiLoading(true);
    try {
      const res = await customerApi.getAiSummary(targetId);
      setAiSummary(res.data);
    } catch {
      setAiSummary(null);
    } finally {
      setAiLoading(false);
    }
  }, [targetId]);

  const loadTimeline = useCallback(async () => {
    setTlLoading(true);
    try {
      const params: any = { limit: 100 };
      if (tlFilter.length) params.categories = tlFilter.join(',');
      if (tlSearch) params.search = tlSearch;
      const res = await customerApi.getTimeline(targetId, params);
      setTimeline(res.data?.events || []);
    } catch {
      setTimeline([]);
    } finally {
      setTlLoading(false);
    }
  }, [targetId, tlFilter, tlSearch]);

  useEffect(() => { load360(); loadAiSummary(); }, [load360, loadAiSummary]);
  useEffect(() => { loadTimeline(); }, [loadTimeline]);

  const sendAskAI = async () => {
    if (!askQuestion.trim()) return;
    const q = askQuestion.trim();
    setAskQuestion('');
    setAskHistory((h) => [...h, { role: 'user', content: q }]);
    setAskLoading(true);
    try {
      const res = await customerApi.askAi(targetId, {
        question: q,
        history: askHistory,
      });
      setAskHistory((h) => [...h, { role: 'assistant', content: res.data?.answer || 'No response.' }]);
    } catch {
      setAskHistory((h) => [...h, { role: 'assistant', content: 'Failed to get AI response.' }]);
    } finally {
      setAskLoading(false);
    }
  };


  const handleInitiateConversation = async () => {
    if (!commMessage.trim()) return;
    setCommSending(true);
    try {
      const res = await customerApi.initiateConversation(targetId, {
        channel: commChannel,
        message: commMessage.trim(),
      });
      setShowNewComm(false);
      setCommMessage('');
      // Navigate to Communications tab and open the new conversation
      setActiveTab('Communications');
      setActiveConvId(res.data.id);
      setActiveConvMessages([res.data.message]);
      // Reload data to show in the conversations list
      load360();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to send message');
    } finally {
      setCommSending(false);
    }
  };

  const handleOpenConversation = async (convId: number) => {
    try {
      const res = await conversationsApi.get(convId);
      setActiveConvId(convId);
      setActiveConvMessages(res.data.messages || []);
    } catch {
      console.error('Failed to load conversation');
    }
  };

  const handleSendInlineMessage = async () => {
    if (!inlineMsg.trim() || !activeConvId) return;
    setInlineSending(true);
    try {
      const res = await customerApi.staffSendMessage(targetId, activeConvId, inlineMsg.trim());
      setActiveConvMessages((prev) => [...prev, res.data]);
      setInlineMsg('');
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to send message');
    } finally {
      setInlineSending(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-96 text-[var(--color-text-muted)]">Loading customer data...</div>;
  }
  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-4">
        <p className="text-[var(--color-text-muted)]">Customer not found</p>
        <Button onClick={() => navigate('/backoffice/customers')}>Back to Customers</Button>
      </div>
    );
  }

  const u = data.user || {};
  const p = data.profile || {};
  const qs: QuickStats = data.quick_stats || {};
  const apps = data.applications || [];
  const payments = data.payments || [];
  const schedules = data.payment_schedules || [];
  const decisions = data.decisions || [];
  const disbursements = data.disbursements || [];
  const colRecords = data.collection_records || [];
  const colChats = data.collection_chats || [];
  const documents = data.documents || [];
  const creditReports = data.credit_reports || [];
  const conversations = data.conversations || [];
  const comments = data.comments || [];
  const notes = data.notes || [];
  const bureauAlerts = data.credit_bureau_alerts || [];
  const auditLogs = data.audit_logs || [];

  // Risk tier
  const riskTier = qs.worst_dpd > 60 ? 'Critical' : qs.worst_dpd > 30 ? 'Watch' : qs.worst_dpd > 0 ? 'Fair' : qs.payment_success_rate >= 90 ? 'Excellent' : 'Good';
  const riskColor = { Excellent: 'success', Good: 'info', Fair: 'warning', Watch: 'warning', Critical: 'danger' }[riskTier] as any;

  return (
    <div className="space-y-0">
      {/* ─── HEADER BAR ─────────────────────────────────────── */}
      <div className="bg-[var(--color-surface)] border-b border-[var(--color-border)] px-6 py-4 -mx-6 -mt-6 mb-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-4">
            <button onClick={() => navigate('/backoffice/customers')} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-sky-400 to-cyan-300 flex items-center justify-center text-lg font-bold text-[#0a1628]">
              {(u.first_name?.[0] || '').toUpperCase()}{(u.last_name?.[0] || '').toUpperCase()}
            </div>
            <div>
              <h1 className="text-xl font-bold">{u.first_name} {u.last_name}</h1>
              <div className="flex items-center gap-3 text-sm text-[var(--color-text-muted)]">
                <span>ID: {u.id}</span>
                <span className="flex items-center gap-1">
                  {idRevealed ? (p.national_id || '—') : maskId(p.national_id)}
                  <button onClick={() => setIdRevealed(!idRevealed)} className="ml-1 hover:text-[var(--color-text)]">
                    {idRevealed ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={u.is_active ? 'success' : 'danger'}>{u.is_active ? 'Active' : 'Inactive'}</Badge>
            <Badge variant={riskColor}>{riskTier}</Badge>
            <Button variant="ghost" size="sm" onClick={() => setShowAskAI(true)}>
              <Sparkles className="w-4 h-4 mr-1" /> Ask AI
            </Button>
            <Button variant="outline" size="sm" onClick={() => setShowNewComm(true)}>
              <MessageCircle className="w-4 h-4 mr-1" /> New Communication
            </Button>
            <Link to={`/backoffice/new-application?customer=${u.id}`}>
              <Button variant="outline" size="sm"><Plus className="w-4 h-4 mr-1" /> New Application</Button>
            </Link>
          </div>
        </div>
      </div>

      {/* ─── BODY: AI PANEL + MAIN TABS ─────────────────────── */}
      <div className="flex gap-6">
        {/* ─── AI INTELLIGENCE PANEL (Sidebar) ─── */}
        <aside className="w-80 shrink-0 space-y-4 hidden lg:block">
          {/* AI Summary */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-amber-400" /> AI Account Summary
              </h2>
              <button onClick={loadAiSummary} disabled={aiLoading} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                <RefreshCw className={`w-4 h-4 ${aiLoading ? 'animate-spin' : ''}`} />
              </button>
            </div>
            {aiLoading && !aiSummary ? (
              <div className="text-sm text-[var(--color-text-muted)] py-4 text-center">Generating summary...</div>
            ) : aiSummary ? (
              <div className="space-y-3 text-sm">
                <div className="flex items-center gap-2">
                  <span className={`capitalize font-medium ${SENTIMENT_COLORS[aiSummary.sentiment] || ''}`}>
                    {aiSummary.sentiment}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-xs ${SENTIMENT_BG[aiSummary.sentiment] || ''} ${SENTIMENT_COLORS[aiSummary.sentiment] || ''}`}>
                    Confidence: {Math.round((aiSummary.confidence_score || 0) * 100)}%
                  </span>
                </div>
                <p className="text-[var(--color-text-muted)] leading-relaxed">{aiSummary.summary_text}</p>
                {aiSummary.highlights?.length > 0 && (
                  <ul className="space-y-1 text-[var(--color-text-muted)]">
                    {aiSummary.highlights.map((h, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <span className="text-sky-400 mt-0.5">*</span> {h}
                      </li>
                    ))}
                  </ul>
                )}
                {aiSummary.risk_narrative && (
                  <div className="p-2 rounded bg-[var(--color-bg)] text-xs">
                    <span className="font-medium text-amber-400">Risk: </span>
                    {aiSummary.risk_narrative}
                  </div>
                )}
                {aiSummary.recommendations?.length > 0 && (
                  <div>
                    <p className="font-medium text-xs mb-1">Recommendations</p>
                    {aiSummary.recommendations.map((r, i) => (
                      <div key={i} className="flex items-start gap-2 mb-1">
                        <span className={`text-xs mt-0.5 ${PRIORITY_COLORS[r.priority] || ''}`}>[{r.priority}]</span>
                        <span className="text-xs text-[var(--color-text-muted)]">{r.text}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-[var(--color-text-muted)]">No AI summary available.</p>
            )}
          </Card>

          {/* Quick Stats */}
          <div className="grid grid-cols-2 gap-2">
            <StatCard label="Lifetime Value" value={fmtMoney(qs.total_lifetime_value)} icon={<TrendingUp className="w-4 h-4 text-emerald-400" />} />
            <StatCard label="Active Products" value={String(qs.active_products || 0)} sub={fmtMoney(qs.total_outstanding)} icon={<Activity className="w-4 h-4 text-sky-400" />} />
            <StatCard label="Worst DPD" value={String(qs.worst_dpd || 0)} icon={<AlertTriangle className={`w-4 h-4 ${qs.worst_dpd > 0 ? 'text-red-400' : 'text-emerald-400'}`} />} />
            <StatCard label="On-time Rate" value={`${qs.payment_success_rate ?? 100}%`} icon={<CheckCircle className="w-4 h-4 text-sky-400" />} />
            <StatCard label="Relationship" value={`${Math.floor((qs.relationship_length_days || 0) / 30)}m`} icon={<Calendar className="w-4 h-4 text-purple-400" />} />
            <StatCard label="Last Contact" value={qs.last_contact ? fmtDate(qs.last_contact) : 'None'} sub={qs.last_contact_channel || ''} icon={<Phone className="w-4 h-4 text-amber-400" />} />
          </div>
        </aside>

        {/* ─── MAIN CONTENT (Tabbed) ─── */}
        <div className="flex-1 min-w-0">
          {/* Tab Bar */}
          <div className="flex gap-1 overflow-x-auto border-b border-[var(--color-border)] mb-4 pb-px">
            {TABS.map((t) => {
              const newAlertCount = t === 'Bureau Alerts' ? bureauAlerts.filter((a: any) => a.status === 'new').length : 0;
              return (
                <button
                  key={t}
                  onClick={() => setActiveTab(t)}
                  className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition flex items-center gap-1.5 ${
                    activeTab === t
                      ? 'border-[var(--color-primary)] text-[var(--color-primary)]'
                      : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
                  }`}
                >
                  {t}
                  {newAlertCount > 0 && (
                    <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-red-500 text-white leading-none">
                      {newAlertCount}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Tab Content */}
          {activeTab === 'Overview' && (
            <OverviewTab
              u={u} p={p} qs={qs} apps={apps} payments={payments}
              schedules={schedules} creditReports={creditReports}
              timeline={timeline} tlLoading={tlLoading} tlFilter={tlFilter}
              setTlFilter={setTlFilter} tlSearch={tlSearch} setTlSearch={setTlSearch}
              targetId={targetId} loadData={load360}
            />
          )}
          {activeTab === 'Applications' && <ApplicationsTab apps={apps} decisions={decisions} />}
          {activeTab === 'Loans' && <LoansTab apps={apps} schedules={schedules} disbursements={disbursements} />}
          {activeTab === 'Payments' && <PaymentsTab payments={payments} schedules={schedules} />}
          {activeTab === 'Collections' && <CollectionsTab records={colRecords} chats={colChats} />}
          {activeTab === 'Communications' && (
            <CommunicationsTab
              conversations={conversations}
              comments={comments}
              notes={notes}
              userId={targetId}
              onStartNew={() => setShowNewComm(true)}
              activeConvId={activeConvId}
              activeConvMessages={activeConvMessages}
              onOpenConversation={handleOpenConversation}
              onCloseConversation={() => { setActiveConvId(null); setActiveConvMessages([]); }}
              inlineMsg={inlineMsg}
              setInlineMsg={setInlineMsg}
              inlineSending={inlineSending}
              onSendInlineMessage={handleSendInlineMessage}
            />
          )}
          {activeTab === 'Documents' && <DocumentsTab documents={documents} apps={apps} />}
          {activeTab === 'Bureau Alerts' && <BureauAlertsTab alerts={bureauAlerts} userId={targetId} onRefresh={load360} />}
          {activeTab === 'Audit Trail' && <AuditTab logs={auditLogs} />}
        </div>
      </div>

      {/* ─── NEW COMMUNICATION MODAL ──────────────────────────── */}
      {showNewComm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] shadow-2xl w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-5">
              <h3 className="font-semibold text-lg flex items-center gap-2">
                <MessageCircle className="w-5 h-5 text-[var(--color-primary)]" />
                New Communication
              </h3>
              <button onClick={() => setShowNewComm(false)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-sm text-[var(--color-text-muted)] mb-4">
              Send a message to <span className="font-medium text-[var(--color-text)]">{u.first_name} {u.last_name}</span>
            </p>

            {/* Channel selector */}
            <div className="mb-4">
              <label className="text-xs font-medium text-[var(--color-text-muted)] mb-2 block">Channel</label>
              <div className="flex gap-2">
                <button
                  onClick={() => setCommChannel('web')}
                  className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg border text-sm font-medium transition ${
                    commChannel === 'web'
                      ? 'border-[var(--color-primary)] bg-[var(--color-primary)]/10 text-[var(--color-primary)]'
                      : 'border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-text-muted)]'
                  }`}
                >
                  <MessageCircle className="w-4 h-4" />
                  Web Chat
                </button>
                <button
                  onClick={() => setCommChannel('whatsapp')}
                  className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg border text-sm font-medium transition ${
                    commChannel === 'whatsapp'
                      ? 'border-emerald-500 bg-emerald-500/10 text-emerald-400'
                      : 'border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-text-muted)]'
                  }`}
                >
                  <Phone className="w-4 h-4" />
                  WhatsApp
                </button>
              </div>
              {commChannel === 'whatsapp' && !(u.best_phone || u.phone) && (
                <p className="text-xs text-red-400 mt-2">This customer has no phone number on file. WhatsApp is not available.</p>
              )}
              {commChannel === 'whatsapp' && (u.best_phone || u.phone) && (
                <p className="text-xs text-[var(--color-text-muted)] mt-2">Will be sent to {u.best_phone || u.phone}</p>
              )}
            </div>

            {/* Message */}
            <div className="mb-5">
              <label className="text-xs font-medium text-[var(--color-text-muted)] mb-2 block">Message</label>
              <textarea
                value={commMessage}
                onChange={(e) => setCommMessage(e.target.value)}
                rows={4}
                placeholder="Type your message to the customer..."
                className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] resize-none"
              />
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-3">
              <Button variant="ghost" onClick={() => setShowNewComm(false)}>Cancel</Button>
              <Button
                variant="primary"
                onClick={handleInitiateConversation}
                disabled={commSending || !commMessage.trim() || (commChannel === 'whatsapp' && !(u.best_phone || u.phone))}
                className="flex items-center gap-2"
              >
                {commSending ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
                {commSending ? 'Sending...' : 'Send Message'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ─── ASK AI SLIDE-OUT ─────────────────────────────────── */}
      {showAskAI && (
        <div className="fixed inset-y-0 right-0 w-96 bg-[var(--color-surface)] border-l border-[var(--color-border)] shadow-2xl z-50 flex flex-col">
          <div className="flex items-center justify-between p-4 border-b border-[var(--color-border)]">
            <h3 className="font-semibold flex items-center gap-2"><Sparkles className="w-4 h-4 text-amber-400" /> Ask AI About This Customer</h3>
            <button onClick={() => setShowAskAI(false)}><X className="w-5 h-5" /></button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {askHistory.length === 0 && (
              <p className="text-sm text-[var(--color-text-muted)] text-center mt-8">Ask any question about this customer. The AI has access to their full profile, loans, payments, and communications.</p>
            )}
            {askHistory.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                  m.role === 'user'
                    ? 'bg-[var(--color-primary)] text-white'
                    : 'bg-[var(--color-bg)] text-[var(--color-text)]'
                }`}>
                  {m.content}
                </div>
              </div>
            ))}
            {askLoading && (
              <div className="flex justify-start">
                <div className="bg-[var(--color-bg)] rounded-lg px-3 py-2 text-sm text-[var(--color-text-muted)]">Thinking...</div>
              </div>
            )}
          </div>
          <div className="p-4 border-t border-[var(--color-border)] flex gap-2">
            <input
              value={askQuestion}
              onChange={(e) => setAskQuestion(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && sendAskAI()}
              placeholder="Ask a question..."
              className="flex-1 px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
            />
            <button onClick={sendAskAI} disabled={askLoading || !askQuestion.trim()} className="px-3 py-2 rounded-lg bg-[var(--color-primary)] text-white disabled:opacity-50">
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Stat Card ────────────────────────────────────────────────────────────
function StatCard({ label, value, sub, icon }: { label: string; value: string; sub?: string; icon: React.ReactNode }) {
  return (
    <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-3">
      <div className="flex items-center gap-1.5 mb-1">{icon}<span className="text-xs text-[var(--color-text-muted)]">{label}</span></div>
      <p className="text-lg font-semibold">{value}</p>
      {sub && <p className="text-xs text-[var(--color-text-muted)]">{sub}</p>}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// TAB: Overview
// ══════════════════════════════════════════════════════════════════════════
function OverviewTab({ u, p, qs, apps, payments, schedules, creditReports, timeline, tlLoading, tlFilter, setTlFilter, tlSearch, setTlSearch, targetId, loadData }: any) {
  // Charts data
  const exposureData = apps
    .filter((a: any) => a.status === 'disbursed')
    .map((a: any, i: number) => ({
      name: a.reference_number || `Loan ${a.id}`,
      value: Number(a.amount_approved || a.amount_requested || 0),
    }));

  // Payment behavior last 12 months
  const now = new Date();
  const monthLabels: string[] = [];
  for (let i = 11; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    monthLabels.push(d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' }));
  }
  const paymentBehavior = monthLabels.map((label, idx) => {
    const d = new Date(now.getFullYear(), now.getMonth() - (11 - idx), 1);
    const m = d.getMonth();
    const y = d.getFullYear();
    let onTime = 0, late = 0, missed = 0;
    schedules.forEach((s: any) => {
      const due = new Date(s.due_date);
      if (due.getMonth() === m && due.getFullYear() === y) {
        if (s.status === 'paid') onTime++;
        else if (s.status === 'partial') late++;
        else if (s.status === 'overdue') missed++;
      }
    });
    return { month: label, 'On Time': onTime, Late: late, Missed: missed };
  });

  const categories = ['application', 'loan', 'payment', 'collection', 'communication', 'document', 'system'];

  return (
    <div className="space-y-6">
      {/* Profile Card */}
      <Card>
        <h3 className="font-semibold mb-3">Customer Profile</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div className="space-y-2">
            <p className="text-[var(--color-text-muted)]">Personal</p>
            <Info label="Full Name" value={`${u.first_name} ${u.last_name}`} />
            <Info label="Email" value={u.email} />
            <Info label="Date of Birth" value={fmtDate(p.date_of_birth)} />
            <Info label="Gender" value={p.gender} />
            <Info label="Marital Status" value={p.marital_status} />
          </div>
          <div className="space-y-2">
            <p className="text-[var(--color-text-muted)]">Employment</p>
            <Info label="Employer" value={p.employer_name} />
            <Info label="Occupation / Job Title" value={p.job_title} />
            <Info label="Type" value={p.employment_type} />
            <Info label="Years" value={p.years_employed} />
            <Info label="Monthly Income" value={fmtMoney(p.monthly_income)} />
            <Info label="Other Income" value={fmtMoney(p.other_income)} />
          </div>
          <div className="space-y-2">
            <p className="text-[var(--color-text-muted)]">Address & KYC</p>
            <Info label="Address" value={[p.address_line1, p.address_line2, p.city, p.parish].filter(Boolean).join(', ')} />
            <Info label="Country" value={p.country} />
            <Info label="ID Type" value={p.id_type} />
            <Info label="ID Verified" value={p.id_verified ? 'Yes' : 'No'} />
            <Info label="Verification" value={p.id_verification_status} />
          </div>
        </div>
      </Card>

      {/* Contact Information Card — Editable (separate component to avoid Vite React Refresh transform bug) */}
      <ContactInfoCard user={u} profile={p} uid={targetId} refresh={loadData} />

      {/* Financial Snapshot */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {exposureData.length > 0 && (
          <Card>
            <h3 className="font-semibold mb-3 text-sm">Exposure Breakdown</h3>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={exposureData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}>
                  {exposureData.map((_: any, i: number) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={(v: any) => fmtMoney(v)} />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        )}
        <Card>
          <h3 className="font-semibold mb-3 text-sm">Payment Behavior (Last 12 Months)</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={paymentBehavior}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
              <Tooltip />
              <Legend iconSize={10} wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="On Time" fill="#34d399" stackId="a" />
              <Bar dataKey="Late" fill="#fb923c" stackId="a" />
              <Bar dataKey="Missed" fill="#f87171" stackId="a" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Summary row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MiniStat label="Total Ever Borrowed" value={fmtMoney(apps.reduce((s: number, a: any) => s + Number(a.amount_approved || a.amount_requested || 0), 0))} />
        <MiniStat label="Total Repaid" value={fmtMoney(payments.filter((p: any) => p.status === 'completed').reduce((s: number, p: any) => s + Number(p.amount || 0), 0))} />
        <MiniStat label="Total Outstanding" value={fmtMoney(qs.total_outstanding)} />
        <MiniStat label="Next Payment" value={(() => {
          const upcoming = schedules.filter((s: any) => s.status === 'upcoming' || s.status === 'due').sort((a: any, b: any) => a.due_date?.localeCompare(b.due_date));
          return upcoming[0] ? `${fmtMoney(upcoming[0].amount_due)} on ${fmtDate(upcoming[0].due_date)}` : 'None';
        })()} />
      </div>

      {/* Credit Score Trend */}
      {creditReports.length > 0 && (
        <Card>
          <h3 className="font-semibold mb-3 text-sm">Credit Score Trend</h3>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={creditReports.filter((c: any) => c.bureau_score).reverse().map((c: any) => ({ date: fmtDate(c.pulled_at), score: c.bureau_score }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} />
              <YAxis domain={['auto', 'auto']} tick={{ fontSize: 10 }} />
              <Tooltip />
              <Line type="monotone" dataKey="score" stroke="#38bdf8" strokeWidth={2} dot />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Timeline */}
      <Card>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-sm">Activity Timeline</h3>
        </div>
        {/* Filters */}
        <div className="flex flex-wrap gap-1.5 mb-3">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setTlFilter((prev: string[]) => prev.includes(cat) ? prev.filter((c: string) => c !== cat) : [...prev, cat])}
              className={`px-2.5 py-1 rounded-full text-xs font-medium transition border ${
                tlFilter.includes(cat)
                  ? 'border-[var(--color-primary)] text-[var(--color-primary)] bg-[var(--color-primary)]/10'
                  : 'border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
        <div className="mb-3">
          <input
            value={tlSearch}
            onChange={(e) => setTlSearch(e.target.value)}
            placeholder="Search timeline..."
            className="w-full px-3 py-1.5 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-xs focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
          />
        </div>
        {tlLoading ? (
          <p className="text-sm text-[var(--color-text-muted)] text-center py-4">Loading...</p>
        ) : timeline.length === 0 ? (
          <p className="text-sm text-[var(--color-text-muted)] text-center py-4">No events found.</p>
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {timeline.map((ev: TimelineEvent, i: number) => {
              const evLink =
                (ev.entity_type === 'loan_application' || ev.entity_type === 'payment' || ev.entity_type === 'schedule') ? `/backoffice/review/${ev.entity_id}` :
                ev.entity_type === 'collection_record' || ev.entity_type === 'collection_chat' ? `/backoffice/collections/${ev.entity_id}` :
                ev.entity_type === 'conversation' ? `/backoffice/conversations/${ev.entity_id}` :
                null;
              return (
                <div key={i} className="flex items-start gap-3 py-2 border-b border-[var(--color-border)] last:border-0 text-sm">
                  <div className="mt-0.5 text-[var(--color-text-muted)]">{CATEGORY_ICONS[ev.category] || <Activity className="w-4 h-4" />}</div>
                  <div className="flex-1 min-w-0">
                    {evLink ? (
                      <Link to={evLink} className="font-medium text-[var(--color-primary)] hover:underline">{ev.title}</Link>
                    ) : (
                      <p className="font-medium">{ev.title}</p>
                    )}
                    {ev.description && <p className="text-xs text-[var(--color-text-muted)] truncate">{ev.description}</p>}
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-xs text-[var(--color-text-muted)]">{fmtDateTime(ev.timestamp)}</p>
                    <p className="text-[10px] text-[var(--color-text-muted)]">{ev.actor}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}

// ── Contact Info Card (extracted to avoid Vite React Refresh transform bug in large components) ──
function ContactInfoCard({ user: u, profile: p, uid, refresh }: { user: any; profile: any; uid: number; refresh: () => void }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const startEdit = () => {
    setForm({
      phone: u.phone || '',
      whatsapp_number: p.whatsapp_number || '',
      contact_email: p.contact_email || '',
      mobile_phone: p.mobile_phone || '',
      home_phone: p.home_phone || '',
      employer_phone: p.employer_phone || '',
    });
    setEditing(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      await customerApi.updateContact(uid, form);
      setEditing(false);
      refresh();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold flex items-center gap-2"><Phone className="w-4 h-4" /> Contact Information</h3>
        {!editing ? (
          <button onClick={startEdit} className="flex items-center gap-1 text-xs text-[var(--color-primary)] hover:underline">
            <Edit3 className="w-3.5 h-3.5" /> Edit
          </button>
        ) : (
          <div className="flex items-center gap-2">
            <button onClick={() => setEditing(false)} className="flex items-center gap-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
              <XCircle className="w-3.5 h-3.5" /> Cancel
            </button>
            <button onClick={save} disabled={saving} className="flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300 disabled:opacity-50">
              <Save className="w-3.5 h-3.5" /> {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        )}
      </div>
      {!editing ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div className="space-y-2">
            <Info label="Primary Phone" value={u.phone || u.best_phone} />
            <Info label="WhatsApp Number" value={p.whatsapp_number} />
          </div>
          <div className="space-y-2">
            <Info label="Mobile Phone" value={p.mobile_phone} />
            <Info label="Home Phone" value={p.home_phone} />
          </div>
          <div className="space-y-2">
            <Info label="Contact Email" value={p.contact_email} />
            <Info label="Employer Phone" value={p.employer_phone} />
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div className="space-y-3">
            <ContactField label="Primary Phone" field="phone" value={form.phone} onChange={(v) => setForm(f => ({ ...f, phone: v }))} />
            <ContactField label="WhatsApp Number" field="whatsapp_number" value={form.whatsapp_number} onChange={(v) => setForm(f => ({ ...f, whatsapp_number: v }))} />
          </div>
          <div className="space-y-3">
            <ContactField label="Mobile Phone" field="mobile_phone" value={form.mobile_phone} onChange={(v) => setForm(f => ({ ...f, mobile_phone: v }))} />
            <ContactField label="Home Phone" field="home_phone" value={form.home_phone} onChange={(v) => setForm(f => ({ ...f, home_phone: v }))} />
          </div>
          <div className="space-y-3">
            <ContactField label="Contact Email" field="contact_email" value={form.contact_email} onChange={(v) => setForm(f => ({ ...f, contact_email: v }))} />
            <ContactField label="Employer Phone" field="employer_phone" value={form.employer_phone} onChange={(v) => setForm(f => ({ ...f, employer_phone: v }))} />
          </div>
        </div>
      )}
    </Card>
  );
}

// Helper sub-components
function Info({ label, value }: { label: string; value: any }) {
  return (
    <div className="flex justify-between">
      <span className="text-[var(--color-text-muted)]">{label}</span>
      <span className="font-medium text-right">{value ?? '—'}</span>
    </div>
  );
}
function ContactField({ label, field, value, onChange }: { label: string; field: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="block text-xs text-[var(--color-text-muted)] mb-1">{label}</label>
      <input
        type={field === 'contact_email' ? 'email' : 'text'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={label}
        className="w-full px-3 py-1.5 text-sm rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
      />
    </div>
  );
}
function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-3 text-center">
      <p className="text-xs text-[var(--color-text-muted)] mb-1">{label}</p>
      <p className="font-semibold text-sm">{value}</p>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// TAB: Applications
// ══════════════════════════════════════════════════════════════════════════
function ApplicationsTab({ apps, decisions }: { apps: any[]; decisions: any[] }) {
  const [expanded, setExpanded] = useState<number | null>(null);
  return (
    <div className="space-y-3">
      {apps.length === 0 && <p className="text-sm text-[var(--color-text-muted)] text-center py-8">No applications found.</p>}
      {apps.map((a: any) => {
        const appDecisions = decisions.filter((d: any) => d.loan_application_id === a.id);
        const isOpen = expanded === a.id;
        return (
          <Card key={a.id}>
            <div className="flex items-center justify-between cursor-pointer" onClick={() => setExpanded(isOpen ? null : a.id)}>
              <div className="flex items-center gap-3">
                <FileText className="w-5 h-5 text-[var(--color-text-muted)]" />
                <div>
                  <p className="font-medium">{a.reference_number}</p>
                  <p className="text-xs text-[var(--color-text-muted)]">{fmtDate(a.submitted_at || a.created_at)} | {fmtMoney(a.amount_requested)}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {getStatusBadge(a.status)}
                <ChevronDown className={`w-4 h-4 transition ${isOpen ? 'rotate-180' : ''}`} />
              </div>
            </div>
            {isOpen && (
              <div className="mt-3 pt-3 border-t border-[var(--color-border)] text-sm space-y-2">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  <Info label="Requested" value={fmtMoney(a.amount_requested)} />
                  <Info label="Approved" value={fmtMoney(a.amount_approved)} />
                  <Info label="Term" value={`${a.term_months}m`} />
                  <Info label="Rate" value={a.interest_rate ? `${a.interest_rate}%` : '—'} />
                  <Info label="Monthly Payment" value={fmtMoney(a.monthly_payment)} />
                  <Info label="Purpose" value={a.purpose?.replace(/_/g, ' ')} />
                  <Info label="Decided" value={fmtDate(a.decided_at)} />
                  <Info label="Disbursed" value={fmtDate(a.disbursed_at)} />
                </div>
                {a.proposed_amount && (
                  <div className="p-2 bg-purple-500/10 rounded text-xs">
                    <span className="text-purple-400 font-medium">Counterproposal: </span>
                    {fmtMoney(a.proposed_amount)} at {a.proposed_rate}% for {a.proposed_term}m — {a.counterproposal_reason}
                  </div>
                )}
                {appDecisions.length > 0 && (
                  <div>
                    <p className="text-xs font-medium mt-2 mb-1">Decision History</p>
                    {appDecisions.map((d: any) => (
                      <div key={d.id} className="text-xs p-2 bg-[var(--color-bg)] rounded mb-1 flex justify-between">
                        <span>Score: {d.credit_score ?? '—'} | Band: {d.risk_band ?? '—'} | Engine: {d.engine_outcome ?? '—'}</span>
                        <span>UW: {d.underwriter_action ?? '—'} | {fmtDate(d.created_at)}</span>
                      </div>
                    ))}
                  </div>
                )}
                <div className="mt-2">
                  <Link to={`/backoffice/review/${a.id}`} className="text-xs text-[var(--color-primary)] hover:underline">
                    View full application →
                  </Link>
                </div>
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// TAB: Loans
// ══════════════════════════════════════════════════════════════════════════
function LoansTab({ apps, schedules, disbursements }: { apps: any[]; schedules: any[]; disbursements: any[] }) {
  const activeLoans = apps.filter((a: any) => a.status === 'disbursed');
  const closedLoans = apps.filter((a: any) => !['draft', 'submitted', 'under_review', 'awaiting_documents', 'credit_check', 'decision_pending', 'disbursed'].includes(a.status) && ['approved', 'accepted', 'offer_sent', 'declined', 'rejected_by_applicant', 'cancelled'].includes(a.status));

  const renderLoan = (a: any) => {
    const loanSchedule = schedules.filter((s: any) => s.loan_application_id === a.id);
    const totalPaid = loanSchedule.reduce((s: number, sc: any) => s + Number(sc.amount_paid || 0), 0);
    const totalDue = loanSchedule.reduce((s: number, sc: any) => s + Number(sc.amount_due || 0), 0);
    const overdue = loanSchedule.filter((s: any) => s.status === 'overdue').length;
    const disb = disbursements.find((d: any) => d.loan_application_id === a.id);

    return (
      <Card key={a.id}>
        <div className="flex items-center justify-between mb-3">
          <div>
            <Link to={`/backoffice/review/${a.id}`} className="font-medium text-[var(--color-primary)] hover:underline">{a.reference_number}</Link>
            <p className="text-xs text-[var(--color-text-muted)]">{a.purpose?.replace(/_/g, ' ')} | {a.term_months}m at {a.interest_rate}%</p>
          </div>
          {getStatusBadge(a.status)}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm mb-3">
          <Info label="Principal" value={fmtMoney(a.amount_approved || a.amount_requested)} />
          <Info label="Monthly" value={fmtMoney(a.monthly_payment)} />
          <Info label="Total Paid" value={fmtMoney(totalPaid)} />
          <Info label="Outstanding" value={fmtMoney(totalDue - totalPaid)} />
        </div>
        {disb && (
          <p className="text-xs text-[var(--color-text-muted)] mb-2">Disbursed: {fmtDate(disb.disbursed_at)} via {disb.method}</p>
        )}
        {overdue > 0 && (
          <p className="text-xs text-red-400 mb-2">{overdue} overdue installment(s)</p>
        )}
        {/* Payment heatmap (simplified) */}
        {loanSchedule.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {loanSchedule.map((s: any, i: number) => (
              <div
                key={i}
                title={`#${s.installment_number} ${s.due_date} — ${s.status}`}
                className={`w-5 h-5 rounded-sm text-[8px] flex items-center justify-center ${
                  s.status === 'paid' ? 'bg-emerald-500/30 text-emerald-400' :
                  s.status === 'overdue' ? 'bg-red-500/30 text-red-400' :
                  s.status === 'partial' ? 'bg-amber-500/30 text-amber-400' :
                  'bg-[var(--color-border)] text-[var(--color-text-muted)]'
                }`}
              >
                {s.installment_number}
              </div>
            ))}
          </div>
        )}
        {/* Action links */}
        <div className="flex items-center gap-4 mt-3 pt-2 border-t border-[var(--color-border)]">
          <Link to={`/backoffice/review/${a.id}`} className="text-xs text-[var(--color-primary)] hover:underline flex items-center gap-1">
            <ExternalLink className="w-3 h-3" /> View Application
          </Link>
          {a.status === 'disbursed' && (
            <Link to={`/backoffice/collections/${a.id}`} className="text-xs text-[var(--color-primary)] hover:underline flex items-center gap-1">
              <Phone className="w-3 h-3" /> Collection Detail
            </Link>
          )}
          {a.consent_signed_at && (
            <button
              onClick={() => downloadBlob(
                loanApi.getConsentPdf(a.id),
                `hire-purchase-agreement-${a.reference_number}.pdf`
              )}
              className="text-xs text-[var(--color-primary)] hover:underline flex items-center gap-1"
            >
              <Download className="w-3 h-3" /> HP Agreement
            </button>
          )}
          <button
            onClick={() => downloadBlob(
              underwriterApi.generateContract(a.id),
              `contract-${a.reference_number}.docx`
            )}
            className="text-xs text-[var(--color-primary)] hover:underline flex items-center gap-1"
          >
            <Scroll className="w-3 h-3" /> Contract
          </button>
        </div>
      </Card>
    );
  };

  return (
    <div className="space-y-4">
      {activeLoans.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-2 text-emerald-400">Active Loans ({activeLoans.length})</h3>
          <div className="space-y-3">{activeLoans.map(renderLoan)}</div>
        </div>
      )}
      {closedLoans.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-2 text-[var(--color-text-muted)]">Closed / Other ({closedLoans.length})</h3>
          <div className="space-y-3">{closedLoans.map(renderLoan)}</div>
        </div>
      )}
      {activeLoans.length === 0 && closedLoans.length === 0 && (
        <p className="text-sm text-[var(--color-text-muted)] text-center py-8">No disbursed loans.</p>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// TAB: Payments
// ══════════════════════════════════════════════════════════════════════════
function PaymentsTab({ payments, schedules }: { payments: any[]; schedules: any[] }) {
  // Payment method distribution
  const methodCounts: Record<string, number> = {};
  payments.forEach((p: any) => { methodCounts[p.payment_type] = (methodCounts[p.payment_type] || 0) + 1; });
  const methodData = Object.entries(methodCounts).map(([name, value]) => ({ name, value }));

  // Payment trend
  const trendData = [...payments].reverse().slice(-30).map((p: any) => ({
    date: fmtDate(p.payment_date),
    amount: Number(p.amount || 0),
  }));

  return (
    <div className="space-y-4">
      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {trendData.length > 0 && (
          <Card>
            <h3 className="font-semibold mb-3 text-sm">Payment Trend</h3>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="date" tick={{ fontSize: 9 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip formatter={(v: any) => fmtMoney(v)} />
                <Line type="monotone" dataKey="amount" stroke="#38bdf8" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        )}
        {methodData.length > 0 && (
          <Card>
            <h3 className="font-semibold mb-3 text-sm">Payment Methods</h3>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={methodData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label>
                  {methodData.map((_: any, i: number) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        )}
      </div>

      {/* Payment Table */}
      <Card padding="none">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-left text-[var(--color-text-muted)]">
                <th className="px-4 py-2 font-medium">Date</th>
                <th className="px-4 py-2 font-medium">Loan</th>
                <th className="px-4 py-2 font-medium text-right">Amount</th>
                <th className="px-4 py-2 font-medium">Type</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Reference</th>
              </tr>
            </thead>
            <tbody>
              {payments.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-[var(--color-text-muted)]">No payments recorded.</td></tr>
              )}
              {payments.map((p: any) => (
                <tr key={p.id} className="border-b border-[var(--color-border)]">
                  <td className="px-4 py-2">{fmtDate(p.payment_date)}</td>
                  <td className="px-4 py-2">
                    <Link to={`/backoffice/review/${p.loan_application_id}`} className="text-[var(--color-primary)] hover:underline">
                      #{p.loan_application_id}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-right font-medium">{fmtMoney(p.amount)}</td>
                  <td className="px-4 py-2">{p.payment_type}</td>
                  <td className="px-4 py-2">{getStatusBadge(p.status)}</td>
                  <td className="px-4 py-2 text-[var(--color-text-muted)] text-xs">{p.reference_number || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// TAB: Collections
// ══════════════════════════════════════════════════════════════════════════
function CollectionsTab({ records, chats }: { records: any[]; chats: any[] }) {
  // Group records by loan
  const loanIds = [...new Set(records.map((r: any) => r.loan_application_id))];

  return (
    <div className="space-y-4">
      {/* Collection Records */}
      <Card>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-sm">Collection Activity ({records.length})</h3>
          {loanIds.length > 0 && (
            <div className="flex items-center gap-2">
              {loanIds.map((id) => (
                <Link key={id} to={`/backoffice/collections/${id}`} className="text-xs text-[var(--color-primary)] hover:underline flex items-center gap-1">
                  <ExternalLink className="w-3 h-3" /> Loan #{id}
                </Link>
              ))}
            </div>
          )}
        </div>
        {records.length === 0 ? (
          <p className="text-sm text-[var(--color-text-muted)] text-center py-4">No collection records.</p>
        ) : (
          <div className="space-y-2">
            {records.map((r: any) => (
              <div key={r.id} className="p-3 bg-[var(--color-bg)] rounded-lg text-sm">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="info">{r.channel}</Badge>
                    <Badge variant={r.outcome === 'promise_to_pay' ? 'success' : r.outcome === 'escalated' ? 'danger' : 'default'}>
                      {r.outcome?.replace(/_/g, ' ')}
                    </Badge>
                    <Link to={`/backoffice/collections/${r.loan_application_id}`} className="text-[10px] text-[var(--color-primary)] hover:underline">
                      Loan #{r.loan_application_id}
                    </Link>
                  </div>
                  <span className="text-xs text-[var(--color-text-muted)]">{fmtDateTime(r.created_at)}</span>
                </div>
                {r.action_taken && <p className="text-xs"><span className="text-[var(--color-text-muted)]">Action:</span> {r.action_taken}</p>}
                {r.notes && <p className="text-xs text-[var(--color-text-muted)] mt-1">{r.notes}</p>}
                {r.promise_amount && (
                  <p className="text-xs mt-1"><span className="text-emerald-400">Promise:</span> {fmtMoney(r.promise_amount)} by {fmtDate(r.promise_date)}</p>
                )}
                {r.next_action_date && (
                  <p className="text-xs text-[var(--color-text-muted)] mt-1">Next action: {fmtDate(r.next_action_date)}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Collection Chats */}
      <Card>
        <h3 className="font-semibold mb-3 text-sm">WhatsApp Chat History ({chats.length})</h3>
        {chats.length === 0 ? (
          <p className="text-sm text-[var(--color-text-muted)] text-center py-4">No chat messages.</p>
        ) : (
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {[...chats].reverse().map((c: any) => (
              <div key={c.id} className={`flex ${c.direction === 'inbound' ? 'justify-start' : 'justify-end'}`}>
                <div className={`max-w-[75%] rounded-lg px-3 py-2 text-sm ${
                  c.direction === 'inbound'
                    ? 'bg-[var(--color-bg)]'
                    : 'bg-emerald-500/15 text-emerald-300'
                }`}>
                  <p>{c.message}</p>
                  <p className="text-[10px] text-[var(--color-text-muted)] mt-1">{fmtDateTime(c.created_at)}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// TAB: Communications
// ══════════════════════════════════════════════════════════════════════════
function CommunicationsTab({
  conversations, comments, notes, userId, onStartNew,
  activeConvId, activeConvMessages, onOpenConversation, onCloseConversation,
  inlineMsg, setInlineMsg, inlineSending, onSendInlineMessage,
}: {
  conversations: any[];
  comments: any[];
  notes: any[];
  userId: number;
  onStartNew: () => void;
  activeConvId: number | null;
  activeConvMessages: Array<{ id: number; role: string; content: string; created_at: string }>;
  onOpenConversation: (id: number) => void;
  onCloseConversation: () => void;
  inlineMsg: string;
  setInlineMsg: (v: string) => void;
  inlineSending: boolean;
  onSendInlineMessage: () => void;
}) {
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeConvMessages]);

  return (
    <div className="space-y-4">
      {/* Start New Communication Button */}
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">Customer Communications</h3>
        <Button variant="primary" size="sm" onClick={onStartNew} className="flex items-center gap-1.5">
          <Plus className="w-4 h-4" /> New Communication
        </Button>
      </div>

      {/* Inline Chat Panel */}
      {activeConvId && (
        <Card>
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-sm flex items-center gap-2">
              <MessageCircle className="w-4 h-4 text-[var(--color-primary)]" />
              Conversation #{activeConvId}
            </h3>
            <div className="flex items-center gap-2">
              <Link to={`/backoffice/conversations/${activeConvId}`} className="text-xs text-[var(--color-primary)] hover:underline flex items-center gap-1">
                <ExternalLink className="w-3 h-3" /> Full View
              </Link>
              <button onClick={onCloseConversation} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="max-h-80 overflow-y-auto space-y-2 mb-3 p-3 rounded-lg bg-[var(--color-bg)]">
            {activeConvMessages.length === 0 && (
              <p className="text-xs text-[var(--color-text-muted)] text-center py-4">No messages yet.</p>
            )}
            {activeConvMessages.map((m) => (
              <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-start' : 'justify-end'}`}>
                <div className={`max-w-[75%] rounded-lg px-3 py-2 text-sm ${
                  m.role === 'user'
                    ? 'bg-[var(--color-surface)] text-[var(--color-text)]'
                    : m.role === 'agent'
                    ? 'bg-[var(--color-primary)]/15 text-[var(--color-primary)]'
                    : 'bg-sky-500/15 text-sky-300'
                }`}>
                  <p className="text-[10px] font-medium mb-0.5 opacity-70">
                    {m.role === 'user' ? 'Customer' : m.role === 'agent' ? 'Staff' : 'AI'}
                  </p>
                  <p>{m.content}</p>
                  <p className="text-[10px] text-[var(--color-text-muted)] mt-1">{fmtDateTime(m.created_at)}</p>
                </div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>

          {/* Reply input */}
          <div className="flex gap-2">
            <input
              value={inlineMsg}
              onChange={(e) => setInlineMsg(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && onSendInlineMessage()}
              placeholder="Type a reply..."
              className="flex-1 px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
            />
            <button
              onClick={onSendInlineMessage}
              disabled={inlineSending || !inlineMsg.trim()}
              className="px-3 py-2 rounded-lg bg-[var(--color-primary)] text-white disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </Card>
      )}

      {/* Conversations */}
      {conversations.length > 0 && (
        <Card>
          <h3 className="font-semibold mb-3 text-sm">Conversations ({conversations.length})</h3>
          {conversations.map((conv: any) => {
            const isActive = activeConvId === conv.id;
            const channelColor = conv.channel === 'whatsapp' ? 'text-emerald-400' : 'text-sky-400';
            return (
              <div key={conv.id} className={`mb-3 p-3 rounded-lg transition ${isActive ? 'bg-[var(--color-primary)]/10 border border-[var(--color-primary)]/30' : 'bg-[var(--color-bg)]'}`}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {conv.channel === 'whatsapp' ? (
                      <Phone className={`w-4 h-4 ${channelColor}`} />
                    ) : (
                      <Bot className={`w-4 h-4 ${channelColor}`} />
                    )}
                    <button
                      onClick={() => onOpenConversation(conv.id)}
                      className="text-sm font-medium text-[var(--color-primary)] hover:underline"
                    >
                      Conversation #{conv.id}
                    </button>
                    <Badge variant={conv.channel === 'whatsapp' ? 'success' : 'info'}>{conv.channel}</Badge>
                    <Badge variant="default">{conv.current_state?.replace(/_/g, ' ')}</Badge>
                  </div>
                  <span className="text-xs text-[var(--color-text-muted)]">{fmtDate(conv.created_at)}</span>
                </div>
                {conv.messages?.slice(-3).map((m: any) => (
                  <div key={m.id} className={`text-xs py-0.5 ${
                    m.role === 'assistant' ? 'text-sky-400' :
                    m.role === 'agent' ? 'text-[var(--color-primary)]' :
                    'text-[var(--color-text)]'
                  }`}>
                    <span className="font-medium">{m.role === 'agent' ? 'Staff' : m.role}: </span>
                    {m.content?.slice(0, 150)}{m.content?.length > 150 ? '...' : ''}
                  </div>
                ))}
                <div className="mt-2 pt-1 border-t border-[var(--color-border)] flex items-center gap-3">
                  <button
                    onClick={() => onOpenConversation(conv.id)}
                    className="text-xs text-[var(--color-primary)] hover:underline flex items-center gap-1"
                  >
                    <MessageCircle className="w-3 h-3" /> Reply Here
                  </button>
                  <Link to={`/backoffice/conversations/${conv.id}`} className="text-xs text-[var(--color-primary)] hover:underline flex items-center gap-1">
                    <ExternalLink className="w-3 h-3" /> Full View
                  </Link>
                </div>
              </div>
            );
          })}
        </Card>
      )}

      {/* Comments */}
      {comments.length > 0 && (
        <Card>
          <h3 className="font-semibold mb-3 text-sm">Application Messages ({comments.length})</h3>
          <div className="space-y-2">
            {comments.map((c: any) => (
              <div key={c.id} className={`p-2 rounded text-sm ${c.is_from_applicant ? 'bg-[var(--color-bg)]' : 'bg-sky-500/10'}`}>
                <div className="flex justify-between mb-1">
                  <span className="text-xs font-medium">
                    {c.is_from_applicant ? 'Customer' : 'Staff'} —{' '}
                    <Link to={`/backoffice/review/${c.application_id}`} className="text-[var(--color-primary)] hover:underline">
                      App #{c.application_id}
                    </Link>
                  </span>
                  <span className="text-xs text-[var(--color-text-muted)]">{fmtDateTime(c.created_at)}</span>
                </div>
                <p className="text-xs text-[var(--color-text-muted)]">{c.content}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Notes */}
      {notes.length > 0 && (
        <Card>
          <h3 className="font-semibold mb-3 text-sm flex items-center gap-1.5"><StickyNote className="w-4 h-4" /> Internal Notes ({notes.length})</h3>
          <div className="space-y-2">
            {notes.map((n: any) => (
              <div key={n.id} className="p-2 bg-amber-500/10 rounded text-sm">
                <div className="flex justify-between mb-1">
                  <span className="text-xs font-medium">
                    Officer #{n.user_id} —{' '}
                    <Link to={`/backoffice/review/${n.application_id}`} className="text-[var(--color-primary)] hover:underline">
                      App #{n.application_id}
                    </Link>
                  </span>
                  <span className="text-xs text-[var(--color-text-muted)]">{fmtDateTime(n.created_at)}</span>
                </div>
                <p className="text-xs">{n.content}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {conversations.length === 0 && comments.length === 0 && notes.length === 0 && (
        <div className="text-center py-12 space-y-3">
          <MessageCircle className="w-10 h-10 text-[var(--color-text-muted)] mx-auto opacity-30" />
          <p className="text-sm text-[var(--color-text-muted)]">No communications found.</p>
          <Button variant="primary" size="sm" onClick={onStartNew} className="inline-flex items-center gap-1.5">
            <Plus className="w-4 h-4" /> Start a Conversation
          </Button>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// TAB: Documents
// ══════════════════════════════════════════════════════════════════════════
function DocumentsTab({ documents, apps }: { documents: any[]; apps: any[] }) {
  const typeIcons: Record<string, React.ReactNode> = {
    national_id: <User className="w-5 h-5" />,
    passport: <User className="w-5 h-5" />,
    drivers_license: <User className="w-5 h-5" />,
    proof_of_income: <Banknote className="w-5 h-5" />,
    bank_statement: <Banknote className="w-5 h-5" />,
    utility_bill: <Building className="w-5 h-5" />,
    employment_letter: <Building className="w-5 h-5" />,
    other: <FileText className="w-5 h-5" />,
  };

  // Applications that have signed consent (hire purchase agreements available)
  const signedApps = apps.filter((a: any) => a.consent_signed_at);

  return (
    <div className="space-y-4">
      {/* Hire Purchase Agreements */}
      {signedApps.length > 0 && (
        <Card>
          <h3 className="font-semibold mb-3 text-sm flex items-center gap-1.5">
            <Scroll className="w-4 h-4 text-sky-400" /> Hire Purchase Agreements
          </h3>
          <div className="space-y-2">
            {signedApps.map((a: any) => (
              <div key={a.id} className="flex items-center justify-between p-2 bg-[var(--color-bg)] rounded-lg">
                <div className="flex items-center gap-3">
                  <Scroll className="w-4 h-4 text-[var(--color-text-muted)]" />
                  <div>
                    <p className="text-sm font-medium">
                      <Link to={`/backoffice/review/${a.id}`} className="text-[var(--color-primary)] hover:underline">
                        {a.reference_number}
                      </Link>
                    </p>
                    <p className="text-xs text-[var(--color-text-muted)]">
                      Signed {fmtDate(a.consent_signed_at)} | {fmtMoney(a.amount_approved || a.amount_requested)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => downloadBlob(
                      loanApi.getConsentPdf(a.id),
                      `hire-purchase-agreement-${a.reference_number}.pdf`
                    )}
                    className="px-2.5 py-1 rounded bg-[var(--color-primary)] text-white text-xs font-medium hover:opacity-90 flex items-center gap-1"
                  >
                    <Download className="w-3 h-3" /> PDF
                  </button>
                  <button
                    onClick={() => downloadBlob(
                      underwriterApi.generateContract(a.id),
                      `contract-${a.reference_number}.docx`
                    )}
                    className="px-2.5 py-1 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-xs font-medium hover:bg-[var(--color-surface-hover)] flex items-center gap-1"
                  >
                    <Download className="w-3 h-3" /> DOCX
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Uploaded Documents */}
      {documents.length === 0 && signedApps.length === 0 ? (
        <p className="text-sm text-[var(--color-text-muted)] text-center py-8">No documents on file.</p>
      ) : documents.length > 0 ? (
        <div>
          <h3 className="font-semibold mb-3 text-sm">Uploaded Documents ({documents.length})</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {documents.map((d: any) => (
              <Card key={d.id}>
                <div className="flex items-start gap-3">
                  <div className="text-[var(--color-text-muted)]">{typeIcons[d.document_type] || <FileText className="w-5 h-5" />}</div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">{d.file_name}</p>
                    <p className="text-xs text-[var(--color-text-muted)]">{d.document_type?.replace(/_/g, ' ')} | {(d.file_size / 1024).toFixed(0)} KB</p>
                    <p className="text-xs text-[var(--color-text-muted)]">
                      <Link to={`/backoffice/review/${d.loan_application_id}`} className="text-[var(--color-primary)] hover:underline">
                        App #{d.loan_application_id}
                      </Link>
                      {' '}| {fmtDate(d.created_at)}
                    </p>
                    <div className="mt-1 flex items-center justify-between">
                      {getStatusBadge(d.status)}
                      <button
                        onClick={() => downloadBlob(
                          underwriterApi.downloadDocument(d.loan_application_id, d.id),
                          d.file_name
                        )}
                        className="text-xs text-[var(--color-primary)] hover:underline flex items-center gap-1"
                      >
                        <Download className="w-3 h-3" /> Download
                      </button>
                    </div>
                    {d.rejection_reason && <p className="text-xs text-red-400 mt-1">{d.rejection_reason}</p>}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// TAB: Bureau Alerts
// ══════════════════════════════════════════════════════════════════════════

const ALERT_TYPE_CONFIG: Record<string, {
  label: string;
  icon: React.ReactNode;
  color: string;
  bg: string;
  description: string;
  actions: Array<{ key: string; label: string; variant: 'primary' | 'warning' | 'danger' | 'info' }>;
}> = {
  new_inquiry: {
    label: 'New Inquiry',
    icon: <Eye className="w-5 h-5" />,
    color: 'text-sky-400',
    bg: 'bg-sky-500/10 border-sky-500/30',
    description: 'Another institution has pulled this customer\'s credit report. They may be shopping for credit elsewhere.',
    actions: [
      { key: 'create_retention_offer', label: 'Create Retention Offer', variant: 'primary' },
      { key: 'schedule_outreach', label: 'Schedule Outreach Call', variant: 'info' },
      { key: 'flag_competitive_threat', label: 'Flag Competitive Threat', variant: 'warning' },
    ],
  },
  new_loan: {
    label: 'New Loan',
    icon: <CreditCard className="w-5 h-5" />,
    color: 'text-amber-400',
    bg: 'bg-amber-500/10 border-amber-500/30',
    description: 'Customer has taken on new credit elsewhere. Total exposure and debt-to-income ratio have increased.',
    actions: [
      { key: 'reassess_credit_limit', label: 'Reassess Credit Limit', variant: 'warning' },
      { key: 'update_exposure', label: 'Update Exposure Profile', variant: 'info' },
      { key: 'recalculate_dti', label: 'Recalculate DTI', variant: 'primary' },
    ],
  },
  new_delinquency: {
    label: 'New Delinquency',
    icon: <AlertTriangle className="w-5 h-5" />,
    color: 'text-orange-400',
    bg: 'bg-orange-500/10 border-orange-500/30',
    description: 'Customer is delinquent at another institution. Early warning — arrears here may follow.',
    actions: [
      { key: 'initiate_early_collection', label: 'Initiate Pre-Collection Contact', variant: 'warning' },
      { key: 'increase_monitoring', label: 'Increase Monitoring', variant: 'info' },
      { key: 'review_exposure', label: 'Review Portfolio Exposure', variant: 'primary' },
      { key: 'freeze_disbursements', label: 'Freeze New Disbursements', variant: 'danger' },
    ],
  },
  default_elsewhere: {
    label: 'Defaulted Elsewhere',
    icon: <Shield className="w-5 h-5" />,
    color: 'text-red-400',
    bg: 'bg-red-500/10 border-red-500/30',
    description: 'Customer has defaulted on credit at another institution. This significantly increases their risk profile.',
    actions: [
      { key: 'freeze_account', label: 'Freeze Account', variant: 'danger' },
      { key: 'trigger_early_collection', label: 'Trigger Early Collection', variant: 'danger' },
      { key: 'reassess_risk_band', label: 'Reassess Risk Band', variant: 'warning' },
      { key: 'escalate_to_management', label: 'Escalate to Management', variant: 'warning' },
    ],
  },
  collection_payment_elsewhere: {
    label: 'Collection Payment Elsewhere',
    icon: <Banknote className="w-5 h-5" />,
    color: 'text-purple-400',
    bg: 'bg-purple-500/10 border-purple-500/30',
    description: 'Customer made a payment to another creditor while in arrears with you. They have funds but are prioritizing others.',
    actions: [
      { key: 'prioritize_collection', label: 'Prioritize for Collection', variant: 'danger' },
      { key: 'adjust_collection_strategy', label: 'Adjust Collection Strategy', variant: 'warning' },
      { key: 'demand_letter', label: 'Send Demand Letter', variant: 'danger' },
      { key: 'record_intelligence', label: 'Record Collection Intel', variant: 'info' },
    ],
  },
};

const SEVERITY_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  low: { label: 'Low', color: 'text-sky-400', bg: 'bg-sky-500/15' },
  medium: { label: 'Medium', color: 'text-amber-400', bg: 'bg-amber-500/15' },
  high: { label: 'High', color: 'text-orange-400', bg: 'bg-orange-500/15' },
  critical: { label: 'Critical', color: 'text-red-400', bg: 'bg-red-500/15' },
};

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  new: { label: 'New', color: 'text-red-400', bg: 'bg-red-500/15' },
  acknowledged: { label: 'Acknowledged', color: 'text-amber-400', bg: 'bg-amber-500/15' },
  action_taken: { label: 'Action Taken', color: 'text-emerald-400', bg: 'bg-emerald-500/15' },
  dismissed: { label: 'Dismissed', color: 'text-[var(--color-text-muted)]', bg: 'bg-[var(--color-bg)]' },
};

function BureauAlertsTab({ alerts, userId, onRefresh }: { alerts: any[]; userId: number; onRefresh: () => void }) {
  const [acting, setActing] = useState<number | null>(null);
  const [actionNotes, setActionNotes] = useState<Record<number, string>>({});
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const handleAction = async (alertId: number, actionKey: string) => {
    setActing(alertId);
    try {
      await customerApi.updateAlert(userId, alertId, {
        action_taken: actionKey,
        action_notes: actionNotes[alertId] || `Action: ${actionKey.replace(/_/g, ' ')}`,
      });
      onRefresh();
    } catch (e) {
      console.error('Failed to update alert', e);
    } finally {
      setActing(null);
    }
  };

  const handleAcknowledge = async (alertId: number) => {
    setActing(alertId);
    try {
      await customerApi.updateAlert(userId, alertId, { status: 'acknowledged' });
      onRefresh();
    } catch (e) {
      console.error('Failed to acknowledge alert', e);
    } finally {
      setActing(null);
    }
  };

  const handleDismiss = async (alertId: number) => {
    setActing(alertId);
    try {
      await customerApi.updateAlert(userId, alertId, {
        status: 'dismissed',
        action_notes: actionNotes[alertId] || 'Dismissed',
      });
      onRefresh();
    } catch (e) {
      console.error('Failed to dismiss alert', e);
    } finally {
      setActing(null);
    }
  };

  const filtered = statusFilter === 'all' ? alerts : alerts.filter((a) => a.status === statusFilter);
  const newCount = alerts.filter((a) => a.status === 'new').length;
  const criticalCount = alerts.filter((a) => a.severity === 'critical' && a.status === 'new').length;

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <h3 className="font-semibold text-sm">Credit Bureau Alerts</h3>
          {newCount > 0 && (
            <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-red-500/15 text-red-400">
              {newCount} new
            </span>
          )}
          {criticalCount > 0 && (
            <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-red-500/15 text-red-400 animate-pulse">
              {criticalCount} critical
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {['all', 'new', 'acknowledged', 'action_taken', 'dismissed'].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium transition border ${
                statusFilter === s
                  ? 'border-[var(--color-primary)] text-[var(--color-primary)] bg-[var(--color-primary)]/10'
                  : 'border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
              }`}
            >
              {s === 'all' ? 'All' : s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
            </button>
          ))}
        </div>
      </div>

      {/* Alert cards */}
      {filtered.length === 0 ? (
        <Card>
          <p className="text-sm text-[var(--color-text-muted)] text-center py-8">
            {alerts.length === 0 ? 'No credit bureau alerts for this customer.' : 'No alerts matching this filter.'}
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {filtered.map((alert: any) => {
            const typeConf = ALERT_TYPE_CONFIG[alert.alert_type] || ALERT_TYPE_CONFIG.new_inquiry;
            const sevConf = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.low;
            const statConf = STATUS_CONFIG[alert.status] || STATUS_CONFIG.new;
            const isNew = alert.status === 'new';
            const isActable = alert.status !== 'action_taken' && alert.status !== 'dismissed';

            return (
              <Card key={alert.id}>
                <div className={`rounded-lg border ${isNew ? typeConf.bg : 'border-[var(--color-border)]'} p-4`}>
                  {/* Header */}
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-start gap-3">
                      <div className={`mt-0.5 ${typeConf.color}`}>{typeConf.icon}</div>
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4 className="font-semibold text-sm">{alert.title}</h4>
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${sevConf.bg} ${sevConf.color}`}>
                            {sevConf.label}
                          </span>
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${statConf.bg} ${statConf.color}`}>
                            {statConf.label}
                          </span>
                        </div>
                        <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
                          {typeConf.label} • {alert.bureau_name} • Ref: {alert.bureau_reference}
                        </p>
                      </div>
                    </div>
                    <div className="text-right shrink-0 ml-3">
                      <p className="text-xs text-[var(--color-text-muted)]">{fmtDateTime(alert.alert_date)}</p>
                      <p className="text-[10px] text-[var(--color-text-muted)]">Received {fmtDateTime(alert.received_at)}</p>
                    </div>
                  </div>

                  {/* Description */}
                  <p className="text-sm text-[var(--color-text-muted)] mb-3 leading-relaxed">{alert.description}</p>

                  {/* Details grid */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3 text-sm">
                    {alert.other_institution && (
                      <div>
                        <span className="text-[10px] text-[var(--color-text-muted)] block">Institution</span>
                        <span className="font-medium text-xs">{alert.other_institution}</span>
                      </div>
                    )}
                    {alert.other_product_type && (
                      <div>
                        <span className="text-[10px] text-[var(--color-text-muted)] block">Product</span>
                        <span className="font-medium text-xs">{alert.other_product_type}</span>
                      </div>
                    )}
                    {alert.other_amount != null && (
                      <div>
                        <span className="text-[10px] text-[var(--color-text-muted)] block">Amount</span>
                        <span className="font-medium text-xs">{fmtMoney(alert.other_amount)}</span>
                      </div>
                    )}
                    {alert.other_delinquency_days != null && (
                      <div>
                        <span className="text-[10px] text-[var(--color-text-muted)] block">Days Past Due</span>
                        <span className="font-medium text-xs text-red-400">{alert.other_delinquency_days} days</span>
                      </div>
                    )}
                    {alert.other_delinquency_amount != null && (
                      <div>
                        <span className="text-[10px] text-[var(--color-text-muted)] block">Delinquent Amount</span>
                        <span className="font-medium text-xs text-red-400">{fmtMoney(alert.other_delinquency_amount)}</span>
                      </div>
                    )}
                  </div>

                  {/* What this means (context box) */}
                  <div className="p-2 rounded bg-[var(--color-bg)] text-xs text-[var(--color-text-muted)] mb-3">
                    <span className="font-medium text-[var(--color-text)]">What this means: </span>
                    {typeConf.description}
                  </div>

                  {/* Action taken display */}
                  {alert.action_taken && (
                    <div className="p-2 rounded bg-emerald-500/10 text-xs mb-3">
                      <span className="font-medium text-emerald-400">Action taken: </span>
                      <span className="text-[var(--color-text)]">{alert.action_taken.replace(/_/g, ' ')}</span>
                      {alert.action_notes && (
                        <p className="text-[var(--color-text-muted)] mt-1">{alert.action_notes}</p>
                      )}
                      <p className="text-[10px] text-[var(--color-text-muted)] mt-1">
                        By User #{alert.acted_by} on {fmtDateTime(alert.acted_at)}
                      </p>
                    </div>
                  )}

                  {/* Action buttons */}
                  {isActable && (
                    <div className="space-y-2">
                      {/* Notes input */}
                      <input
                        value={actionNotes[alert.id] || ''}
                        onChange={(e) => setActionNotes((n) => ({ ...n, [alert.id]: e.target.value }))}
                        placeholder="Add notes before taking action..."
                        className="w-full px-3 py-1.5 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-xs focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                      />
                      <div className="flex items-center gap-2 flex-wrap">
                        {/* Primary actions */}
                        {typeConf.actions.map((action) => {
                          const btnColors =
                            action.variant === 'danger' ? 'bg-red-500/15 text-red-400 hover:bg-red-500/25 border-red-500/30' :
                            action.variant === 'warning' ? 'bg-amber-500/15 text-amber-400 hover:bg-amber-500/25 border-amber-500/30' :
                            action.variant === 'primary' ? 'bg-[var(--color-primary)]/15 text-[var(--color-primary)] hover:bg-[var(--color-primary)]/25 border-[var(--color-primary)]/30' :
                            'bg-sky-500/15 text-sky-400 hover:bg-sky-500/25 border-sky-500/30';
                          return (
                            <button
                              key={action.key}
                              onClick={() => handleAction(alert.id, action.key)}
                              disabled={acting === alert.id}
                              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition ${btnColors} disabled:opacity-50`}
                            >
                              {acting === alert.id ? '...' : action.label}
                            </button>
                          );
                        })}
                        <div className="flex-1" />
                        {/* Secondary actions */}
                        {isNew && (
                          <button
                            onClick={() => handleAcknowledge(alert.id)}
                            disabled={acting === alert.id}
                            className="px-3 py-1.5 rounded-lg text-xs font-medium border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition disabled:opacity-50"
                          >
                            Acknowledge
                          </button>
                        )}
                        <button
                          onClick={() => handleDismiss(alert.id)}
                          disabled={acting === alert.id}
                          className="px-3 py-1.5 rounded-lg text-xs font-medium border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition disabled:opacity-50"
                        >
                          Dismiss
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// TAB: Audit Trail
// ══════════════════════════════════════════════════════════════════════════
function AuditTab({ logs }: { logs: any[] }) {
  const [filterAction, setFilterAction] = useState('');
  const filtered = filterAction ? logs.filter((l: any) => l.action?.toLowerCase().includes(filterAction.toLowerCase())) : logs;

  return (
    <div className="space-y-3">
      <div className="mb-3">
        <input
          value={filterAction}
          onChange={(e) => setFilterAction(e.target.value)}
          placeholder="Filter by action..."
          className="w-full max-w-xs px-3 py-1.5 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-xs focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
        />
      </div>
      <Card padding="none">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-left text-[var(--color-text-muted)]">
                <th className="px-4 py-2 font-medium">Timestamp</th>
                <th className="px-4 py-2 font-medium">Action</th>
                <th className="px-4 py-2 font-medium">Entity</th>
                <th className="px-4 py-2 font-medium">User</th>
                <th className="px-4 py-2 font-medium">Details</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-[var(--color-text-muted)]">No audit entries.</td></tr>
              )}
              {filtered.map((l: any) => {
                const entityLink =
                  l.entity_type === 'loan_application' ? `/backoffice/review/${l.entity_id}` :
                  l.entity_type === 'conversation' ? `/backoffice/conversations/${l.entity_id}` :
                  null;
                return (
                  <tr key={l.id} className="border-b border-[var(--color-border)]">
                    <td className="px-4 py-2 text-xs whitespace-nowrap">{fmtDateTime(l.created_at)}</td>
                    <td className="px-4 py-2 font-medium">{l.action}</td>
                    <td className="px-4 py-2">
                      {entityLink ? (
                        <Link to={entityLink} className="text-[var(--color-primary)] hover:underline">
                          {l.entity_type} #{l.entity_id}
                        </Link>
                      ) : (
                        <span className="text-[var(--color-text-muted)]">{l.entity_type} #{l.entity_id}</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-[var(--color-text-muted)]">{l.user_id ? `User #${l.user_id}` : 'System'}</td>
                    <td className="px-4 py-2 text-xs text-[var(--color-text-muted)] max-w-xs truncate">{l.details || '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
