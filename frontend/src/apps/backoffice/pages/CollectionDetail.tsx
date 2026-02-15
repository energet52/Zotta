import { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, MessageCircle, Phone, Mail, Send, Plus, User,
  Shield, ShieldAlert, AlertCircle, Clock, CheckCircle, XCircle,
  DollarSign, FileText, Handshake, Scale,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import Badge from '../../../components/ui/Badge';
import { collectionsApi, underwriterApi } from '../../../api/endpoints';

interface CollectionRecord {
  id: number;
  agent_name: string;
  channel: string;
  notes: string;
  action_taken: string;
  outcome: string;
  next_action_date: string | null;
  promise_amount: number | null;
  promise_date: string | null;
  created_at: string;
}

interface ChatMessage {
  id: number;
  direction: string;
  message: string;
  status: string;
  created_at: string;
}

interface PTP {
  id: number;
  agent_name: string;
  amount_promised: number;
  promise_date: string;
  payment_method: string | null;
  status: string;
  amount_received: number;
  reminded_at: string | null;
  broken_at: string | null;
  notes: string | null;
  created_at: string;
}

interface Settlement {
  id: number;
  offer_type: string;
  original_balance: number;
  settlement_amount: number;
  discount_pct: number;
  plan_months: number | null;
  plan_monthly_amount: number | null;
  lump_sum: number | null;
  status: string;
  offered_by_name: string | null;
  approved_by_name: string | null;
  approval_required: boolean;
  notes: string | null;
  created_at: string;
}

interface CaseData {
  id: number;
  loan_application_id: number;
  assigned_agent_id: number | null;
  assigned_agent_name: string | null;
  status: string;
  delinquency_stage: string;
  priority_score: number;
  dpd: number;
  total_overdue: number;
  dispute_active: boolean;
  vulnerability_flag: boolean;
  do_not_contact: boolean;
  hardship_flag: boolean;
  next_best_action: string | null;
  nba_confidence: number;
  nba_reasoning: string | null;
  first_contact_at: string | null;
  last_contact_at: string | null;
  sla_first_contact_deadline: string | null;
  sla_next_contact_deadline: string | null;
}

interface ComplianceStatus {
  allowed: boolean;
  reasons: string[];
  next_allowed_at: string | null;
}

const CHANNELS = [
  { value: 'phone', label: 'Phone', icon: Phone },
  { value: 'whatsapp', label: 'WhatsApp', icon: MessageCircle },
  { value: 'email', label: 'Email', icon: Mail },
  { value: 'in_person', label: 'In Person', icon: User },
  { value: 'sms', label: 'SMS', icon: MessageCircle },
];

const OUTCOMES = [
  { value: 'promise_to_pay', label: 'Promise to Pay' },
  { value: 'no_answer', label: 'No Answer' },
  { value: 'disputed', label: 'Disputed' },
  { value: 'payment_arranged', label: 'Payment Arranged' },
  { value: 'escalated', label: 'Escalated' },
  { value: 'other', label: 'Other' },
];

type TabKey = 'overview' | 'history' | 'chat' | 'promises' | 'settlements' | 'compliance';

export default function CollectionDetail() {
  const { id } = useParams<{ id: string }>();
  const appId = parseInt(id || '0');
  const [app, setApp] = useState<any>(null);
  const [caseData, setCaseData] = useState<CaseData | null>(null);
  const [records, setRecords] = useState<CollectionRecord[]>([]);
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [ptps, setPtps] = useState<PTP[]>([]);
  const [settlements, setSettlements] = useState<Settlement[]>([]);
  const [compliance, setCompliance] = useState<ComplianceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabKey>('overview');
  const [showForm, setShowForm] = useState(false);
  const [chatMsg, setChatMsg] = useState('');
  const [sendingChat, setSendingChat] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // PTP Form
  const [showPtpForm, setShowPtpForm] = useState(false);
  const [ptpForm, setPtpForm] = useState({ amount_promised: '', promise_date: '', payment_method: '', notes: '' });

  // Settlement
  const [creatingSettlement, setCreatingSettlement] = useState(false);

  // Interaction form
  const [form, setForm] = useState({
    channel: 'phone', notes: '', action_taken: '', outcome: 'no_answer',
    next_action_date: '', promise_amount: '', promise_date: '',
  });

  useEffect(() => { loadData(); }, [appId]);

  useEffect(() => {
    if (tab !== 'chat') return;
    const interval = setInterval(async () => {
      try { const res = await collectionsApi.getChat(appId); setChat(res.data); } catch { /* ignore */ }
    }, 4000);
    return () => clearInterval(interval);
  }, [appId, tab]);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chat]);

  const loadData = async () => {
    try {
      const [appRes, histRes, chatRes] = await Promise.all([
        underwriterApi.getFullApplication(appId),
        collectionsApi.getHistory(appId),
        collectionsApi.getChat(appId),
      ]);
      setApp(appRes.data);
      setRecords(histRes.data);
      setChat(chatRes.data);

      // Load case data
      try {
        const casesRes = await collectionsApi.listCases({ limit: 1000 });
        const c = casesRes.data.find((cc: CaseData) => cc.loan_application_id === appId);
        if (c) {
          setCaseData(c);
          // Load PTPs, settlements, compliance
          const [ptpRes, settRes] = await Promise.all([
            collectionsApi.listPtps(c.id),
            collectionsApi.listSettlements(c.id),
          ]);
          setPtps(ptpRes.data);
          setSettlements(settRes.data);
          try {
            const compRes = await collectionsApi.checkCompliance({ case_id: c.id, jurisdiction: 'TT' });
            setCompliance(compRes.data);
          } catch { /* ignore */ }
        }
      } catch { /* ignore */ }
    } catch { /* ignore */ }
    setLoading(false);
  };

  const handleAddRecord = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await collectionsApi.addRecord(appId, {
        ...form,
        promise_amount: form.promise_amount ? parseFloat(form.promise_amount) : undefined,
        next_action_date: form.next_action_date || undefined,
        promise_date: form.promise_date || undefined,
      });
      setShowForm(false);
      setForm({ channel: 'phone', notes: '', action_taken: '', outcome: 'no_answer', next_action_date: '', promise_amount: '', promise_date: '' });
      const histRes = await collectionsApi.getHistory(appId);
      setRecords(histRes.data);
    } catch { /* ignore */ }
  };

  const handleSendChat = async () => {
    if (!chatMsg.trim()) return;
    setSendingChat(true);
    try {
      const res = await collectionsApi.sendWhatsApp(appId, { message: chatMsg });
      setChat(prev => [...prev, ...res.data]);
      setChatMsg('');
    } catch { /* ignore */ }
    setSendingChat(false);
  };

  const handleCreatePtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!caseData) return;
    try {
      await collectionsApi.createPtp(caseData.id, {
        amount_promised: parseFloat(ptpForm.amount_promised),
        promise_date: ptpForm.promise_date,
        payment_method: ptpForm.payment_method || undefined,
        notes: ptpForm.notes || undefined,
      });
      setShowPtpForm(false);
      setPtpForm({ amount_promised: '', promise_date: '', payment_method: '', notes: '' });
      const res = await collectionsApi.listPtps(caseData.id);
      setPtps(res.data);
    } catch { /* ignore */ }
  };

  const handleUpdatePtp = async (ptpId: number, newStatus: string) => {
    if (!caseData) return;
    try {
      await collectionsApi.updatePtp(ptpId, { status: newStatus });
      const res = await collectionsApi.listPtps(caseData.id);
      setPtps(res.data);
    } catch { /* ignore */ }
  };

  const handleAutoCalcSettlement = async () => {
    if (!caseData) return;
    setCreatingSettlement(true);
    try {
      await collectionsApi.createSettlement(caseData.id, { auto_calculate: true, offer_type: 'full_payment', settlement_amount: 1 });
      const res = await collectionsApi.listSettlements(caseData.id);
      setSettlements(res.data);
    } catch { /* ignore */ }
    setCreatingSettlement(false);
  };

  const handleApproveSettlement = async (sid: number) => {
    try {
      await collectionsApi.approveSettlement(sid);
      if (caseData) {
        const res = await collectionsApi.listSettlements(caseData.id);
        setSettlements(res.data);
      }
    } catch { /* ignore */ }
  };

  const handleAcceptSettlement = async (sid: number) => {
    try {
      await collectionsApi.acceptSettlement(sid);
      if (caseData) {
        const res = await collectionsApi.listSettlements(caseData.id);
        setSettlements(res.data);
      }
    } catch { /* ignore */ }
  };

  const handleToggleFlag = async (flag: string, value: boolean) => {
    if (!caseData) return;
    try {
      await collectionsApi.updateCase(caseData.id, { [flag]: value });
      // Reload case
      const casesRes = await collectionsApi.listCases({ limit: 1000 });
      const c = casesRes.data.find((cc: CaseData) => cc.loan_application_id === appId);
      if (c) setCaseData(c);
    } catch { /* ignore */ }
  };

  const fmt = (val: number | null | undefined) =>
    val != null ? `TTD ${val.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '—';

  const inputClass = "w-full h-[38px] px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]";

  if (loading) return <div className="flex items-center justify-center h-64 text-[var(--color-text-muted)]">Loading...</div>;
  if (!app) return <div className="text-center text-[var(--color-text-muted)]">Application not found</div>;

  const application = app.application;

  const TABS: { key: TabKey; label: string }[] = [
    { key: 'overview', label: 'Case Overview' },
    { key: 'history', label: 'Interactions' },
    { key: 'chat', label: 'WhatsApp' },
    { key: 'promises', label: 'Promises' },
    { key: 'settlements', label: 'Settlements' },
    { key: 'compliance', label: 'Compliance' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-3">
        <Link to="/backoffice/collections" className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
          <ArrowLeft size={20} />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">Collection: {application.reference_number}</h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            {fmt(application.amount_approved)} at {application.interest_rate}% for {application.term_months} months
          </p>
        </div>
        {caseData && (
          <div className="flex items-center gap-2">
            <Badge variant={caseData.status === 'open' ? 'warning' : caseData.status === 'settled' ? 'success' : 'danger'}>
              {caseData.status.replace(/_/g, ' ')}
            </Badge>
            <Badge variant="info">{caseData.dpd} DPD</Badge>
          </div>
        )}
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <div className="text-xs text-[var(--color-text-muted)]">Overdue</div>
          <div className="text-lg font-bold text-[var(--color-danger)] mt-1">{fmt(caseData?.total_overdue)}</div>
        </Card>
        <Card>
          <div className="text-xs text-[var(--color-text-muted)]">Priority Score</div>
          <div className="text-lg font-bold mt-1">{caseData ? `${(caseData.priority_score * 100).toFixed(0)}%` : '—'}</div>
        </Card>
        <Card>
          <div className="text-xs text-[var(--color-text-muted)]">Agent</div>
          <div className="text-lg font-bold text-[var(--color-primary)] mt-1">{caseData?.assigned_agent_name || 'Unassigned'}</div>
        </Card>
        <Card>
          <div className="text-xs text-[var(--color-text-muted)]">Next Best Action</div>
          <div className="text-sm font-semibold text-amber-400 mt-1 capitalize">{caseData?.next_best_action?.replace(/_/g, ' ') || '—'}</div>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex space-x-1 bg-[var(--color-surface)] rounded-lg p-1 w-fit overflow-x-auto">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors whitespace-nowrap ${
              tab === t.key ? 'bg-[var(--color-primary)] text-white' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Case Overview ─── */}
      {tab === 'overview' && caseData && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* NBA */}
          <Card>
            <h3 className="font-semibold mb-3 flex items-center gap-2"><FileText size={16} /> Next Best Action</h3>
            <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
              <div className="font-semibold text-amber-400 capitalize">{caseData.next_best_action?.replace(/_/g, ' ') || 'No recommendation'}</div>
              <div className="text-xs text-[var(--color-text-muted)] mt-1">
                Confidence: {((caseData.nba_confidence || 0) * 100).toFixed(0)}%
              </div>
              {caseData.nba_reasoning && (
                <p className="text-sm text-[var(--color-text-muted)] mt-2">{caseData.nba_reasoning}</p>
              )}
            </div>
          </Card>

          {/* Flags */}
          <Card>
            <h3 className="font-semibold mb-3 flex items-center gap-2"><Shield size={16} /> Case Flags</h3>
            <div className="space-y-2">
              {[
                { key: 'dispute_active', label: 'Dispute Active', icon: ShieldAlert, color: 'text-purple-400' },
                { key: 'vulnerability_flag', label: 'Vulnerability', icon: AlertCircle, color: 'text-amber-400' },
                { key: 'do_not_contact', label: 'Do Not Contact', icon: Shield, color: 'text-gray-400' },
                { key: 'hardship_flag', label: 'Hardship', icon: User, color: 'text-blue-400' },
              ].map(f => (
                <label key={f.key} className="flex items-center justify-between p-2 rounded-lg hover:bg-[var(--color-surface-hover)] cursor-pointer">
                  <span className={`flex items-center gap-2 text-sm ${f.color}`}>
                    <f.icon size={14} /> {f.label}
                  </span>
                  <input
                    type="checkbox"
                    checked={(caseData as any)[f.key]}
                    onChange={e => handleToggleFlag(f.key, e.target.checked)}
                    className="rounded"
                  />
                </label>
              ))}
            </div>
          </Card>

          {/* SLA */}
          <Card>
            <h3 className="font-semibold mb-3 flex items-center gap-2"><Clock size={16} /> SLA Timers</h3>
            <div className="space-y-3">
              <div>
                <span className="text-xs text-[var(--color-text-muted)]">First Contact Deadline</span>
                <p className="text-sm font-medium">
                  {caseData.sla_first_contact_deadline
                    ? new Date(caseData.sla_first_contact_deadline).toLocaleString()
                    : '—'}
                </p>
              </div>
              <div>
                <span className="text-xs text-[var(--color-text-muted)]">First Contact</span>
                <p className="text-sm font-medium">
                  {caseData.first_contact_at
                    ? new Date(caseData.first_contact_at).toLocaleString()
                    : <span className="text-amber-400">Not yet contacted</span>}
                </p>
              </div>
              <div>
                <span className="text-xs text-[var(--color-text-muted)]">Last Contact</span>
                <p className="text-sm font-medium">
                  {caseData.last_contact_at
                    ? new Date(caseData.last_contact_at).toLocaleString()
                    : '—'}
                </p>
              </div>
            </div>
          </Card>

          {/* Compliance Quick Check */}
          <Card>
            <h3 className="font-semibold mb-3 flex items-center gap-2"><Scale size={16} /> Compliance Status</h3>
            {compliance ? (
              <div>
                <div className={`flex items-center gap-2 text-lg font-bold ${compliance.allowed ? 'text-emerald-400' : 'text-red-400'}`}>
                  {compliance.allowed ? <CheckCircle size={20} /> : <XCircle size={20} />}
                  {compliance.allowed ? 'Contact Permitted' : 'Contact Restricted'}
                </div>
                {compliance.reasons.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {compliance.reasons.map((r, i) => (
                      <li key={i} className="text-sm text-[var(--color-text-muted)] flex items-start gap-1">
                        <XCircle size={12} className="text-red-400 mt-0.5 shrink-0" /> {r}
                      </li>
                    ))}
                  </ul>
                )}
                {compliance.next_allowed_at && (
                  <p className="text-xs text-[var(--color-text-muted)] mt-2">
                    Next allowed: {new Date(compliance.next_allowed_at).toLocaleString()}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-[var(--color-text-muted)]">No compliance data</p>
            )}
          </Card>
        </div>
      )}

      {/* ── Interaction History ─── */}
      {tab === 'history' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button onClick={() => setShowForm(!showForm)}>
              <Plus size={16} className="mr-1" /> Add Interaction
            </Button>
          </div>

          {showForm && (
            <Card>
              <h3 className="font-semibold mb-4">New Collection Interaction</h3>
              <form onSubmit={handleAddRecord} className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-[var(--color-text-muted)] mb-1">Channel</label>
                  <select value={form.channel} onChange={e => setForm(f => ({ ...f, channel: e.target.value }))} className={inputClass}>
                    {CHANNELS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-[var(--color-text-muted)] mb-1">Outcome</label>
                  <select value={form.outcome} onChange={e => setForm(f => ({ ...f, outcome: e.target.value }))} className={inputClass}>
                    {OUTCOMES.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm text-[var(--color-text-muted)] mb-1">Notes</label>
                  <textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} className={inputClass} rows={3} />
                </div>
                <div>
                  <label className="block text-sm text-[var(--color-text-muted)] mb-1">Action Taken</label>
                  <input type="text" value={form.action_taken} onChange={e => setForm(f => ({ ...f, action_taken: e.target.value }))} className={inputClass} />
                </div>
                <div>
                  <label className="block text-sm text-[var(--color-text-muted)] mb-1">Next Action Date</label>
                  <input type="date" value={form.next_action_date} onChange={e => setForm(f => ({ ...f, next_action_date: e.target.value }))} className={inputClass} />
                </div>
                <div>
                  <label className="block text-sm text-[var(--color-text-muted)] mb-1">Promise Amount</label>
                  <input type="number" value={form.promise_amount} onChange={e => setForm(f => ({ ...f, promise_amount: e.target.value }))} className={inputClass} step="0.01" />
                </div>
                <div>
                  <label className="block text-sm text-[var(--color-text-muted)] mb-1">Promise Date</label>
                  <input type="date" value={form.promise_date} onChange={e => setForm(f => ({ ...f, promise_date: e.target.value }))} className={inputClass} />
                </div>
                <div className="md:col-span-2 flex justify-end space-x-2">
                  <Button variant="secondary" type="button" onClick={() => setShowForm(false)}>Cancel</Button>
                  <Button type="submit">Save Record</Button>
                </div>
              </form>
            </Card>
          )}

          <div className="space-y-3">
            {records.map(record => (
              <Card key={record.id}>
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-3">
                    <div className="p-2 bg-[var(--color-primary)]/15 rounded-lg mt-0.5">
                      {record.channel === 'phone' && <Phone size={16} className="text-[var(--color-primary)]" />}
                      {record.channel === 'whatsapp' && <MessageCircle size={16} className="text-emerald-400" />}
                      {record.channel === 'email' && <Mail size={16} className="text-[var(--color-cyan)]" />}
                      {!['phone', 'whatsapp', 'email'].includes(record.channel) && <User size={16} className="text-[var(--color-text-muted)]" />}
                    </div>
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-medium text-sm">{record.agent_name}</span>
                        <Badge variant="info">{record.channel}</Badge>
                        <Badge variant={record.outcome === 'promise_to_pay' || record.outcome === 'payment_arranged' ? 'success' : record.outcome === 'no_answer' ? 'warning' : 'info'}>
                          {record.outcome.replace(/_/g, ' ')}
                        </Badge>
                      </div>
                      {record.notes && <p className="text-sm text-[var(--color-text-muted)] mt-1">{record.notes}</p>}
                      {record.action_taken && <p className="text-xs text-[var(--color-text-muted)] mt-1">Action: {record.action_taken}</p>}
                      {record.promise_amount && (
                        <p className="text-xs text-emerald-400 mt-1">
                          Promise: {fmt(record.promise_amount)} by {record.promise_date}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="text-xs text-[var(--color-text-muted)]">{new Date(record.created_at).toLocaleString()}</div>
                </div>
              </Card>
            ))}
            {records.length === 0 && (
              <div className="text-center text-[var(--color-text-muted)] py-8">No interactions recorded yet</div>
            )}
          </div>
        </div>
      )}

      {/* ── WhatsApp Chat ─── */}
      {tab === 'chat' && (
        <Card className="flex flex-col" style={{ height: '500px' }}>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {chat.length === 0 && (
              <div className="text-center text-[var(--color-text-muted)] py-8">
                No WhatsApp messages yet. Send a message to start the conversation.
              </div>
            )}
            {chat.map(msg => (
              <div key={msg.id} className={`flex ${msg.direction === 'outbound' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[70%] rounded-2xl px-4 py-2 ${
                  msg.direction === 'outbound'
                    ? 'bg-[var(--color-primary)] text-white rounded-br-md'
                    : 'bg-[var(--color-surface-hover)] text-[var(--color-text)] rounded-bl-md'
                }`}>
                  <p className="text-sm">{msg.message}</p>
                  <div className={`text-xs mt-1 ${msg.direction === 'outbound' ? 'text-white/60' : 'text-[var(--color-text-muted)]'}`}>
                    {new Date(msg.created_at).toLocaleTimeString()} · {msg.status}
                  </div>
                </div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>
          <div className="border-t border-[var(--color-border)] p-3 flex space-x-2">
            <input
              type="text" value={chatMsg}
              onChange={e => setChatMsg(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSendChat()}
              placeholder="Type a WhatsApp message..."
              className="flex-1 px-4 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-full text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
              disabled={sendingChat}
            />
            <button
              onClick={handleSendChat}
              disabled={sendingChat || !chatMsg.trim()}
              className="p-2 bg-[var(--color-primary)] text-white rounded-full hover:brightness-110 disabled:opacity-50 transition-all"
            >
              <Send size={18} />
            </button>
          </div>
        </Card>
      )}

      {/* ── Promises to Pay ─── */}
      {tab === 'promises' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button onClick={() => setShowPtpForm(!showPtpForm)} disabled={!caseData}>
              <Plus size={16} className="mr-1" /> New Promise
            </Button>
          </div>

          {showPtpForm && caseData && (
            <Card>
              <h3 className="font-semibold mb-4">Create Promise to Pay</h3>
              <form onSubmit={handleCreatePtp} className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-[var(--color-text-muted)] mb-1">Amount Promised *</label>
                  <input type="number" required min="0.01" step="0.01"
                    value={ptpForm.amount_promised}
                    onChange={e => setPtpForm(f => ({ ...f, amount_promised: e.target.value }))}
                    className={inputClass} />
                </div>
                <div>
                  <label className="block text-sm text-[var(--color-text-muted)] mb-1">Promise Date *</label>
                  <input type="date" required
                    value={ptpForm.promise_date}
                    onChange={e => setPtpForm(f => ({ ...f, promise_date: e.target.value }))}
                    className={inputClass} />
                </div>
                <div>
                  <label className="block text-sm text-[var(--color-text-muted)] mb-1">Payment Method</label>
                  <select value={ptpForm.payment_method}
                    onChange={e => setPtpForm(f => ({ ...f, payment_method: e.target.value }))}
                    className={inputClass}>
                    <option value="">Select...</option>
                    <option value="bank_transfer">Bank Transfer</option>
                    <option value="online">Online</option>
                    <option value="cash">Cash</option>
                    <option value="mobile_money">Mobile Money</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-[var(--color-text-muted)] mb-1">Notes</label>
                  <input type="text"
                    value={ptpForm.notes}
                    onChange={e => setPtpForm(f => ({ ...f, notes: e.target.value }))}
                    className={inputClass} />
                </div>
                <div className="md:col-span-2 flex justify-end space-x-2">
                  <Button variant="secondary" type="button" onClick={() => setShowPtpForm(false)}>Cancel</Button>
                  <Button type="submit">Create Promise</Button>
                </div>
              </form>
            </Card>
          )}

          <div className="space-y-3">
            {ptps.map(p => (
              <Card key={p.id}>
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{fmt(p.amount_promised)}</span>
                      <Badge variant={
                        p.status === 'kept' ? 'success' :
                        p.status === 'broken' ? 'danger' :
                        p.status === 'pending' ? 'warning' : 'info'
                      }>
                        {p.status}
                      </Badge>
                    </div>
                    <p className="text-sm text-[var(--color-text-muted)] mt-1">
                      Due: {new Date(p.promise_date).toLocaleDateString()} · By: {p.agent_name}
                      {p.payment_method && ` · ${p.payment_method}`}
                    </p>
                    {p.amount_received > 0 && (
                      <p className="text-xs text-emerald-400 mt-1">Received: {fmt(p.amount_received)}</p>
                    )}
                    {p.notes && <p className="text-xs text-[var(--color-text-muted)] mt-1">{p.notes}</p>}
                    {p.broken_at && <p className="text-xs text-red-400 mt-1">Broken at: {new Date(p.broken_at).toLocaleString()}</p>}
                  </div>
                  <div className="flex gap-1">
                    {p.status === 'pending' && (
                      <>
                        <button onClick={() => handleUpdatePtp(p.id, 'kept')}
                          className="px-2 py-1 text-xs rounded bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30">
                          Kept
                        </button>
                        <button onClick={() => handleUpdatePtp(p.id, 'broken')}
                          className="px-2 py-1 text-xs rounded bg-red-500/20 text-red-400 hover:bg-red-500/30">
                          Broken
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </Card>
            ))}
            {ptps.length === 0 && (
              <div className="text-center text-[var(--color-text-muted)] py-8">No promises recorded yet</div>
            )}
          </div>
        </div>
      )}

      {/* ── Settlements ─── */}
      {tab === 'settlements' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button onClick={handleAutoCalcSettlement} disabled={!caseData || creatingSettlement}>
              <DollarSign size={16} className="mr-1" /> {creatingSettlement ? 'Calculating...' : 'Calculate Options'}
            </Button>
          </div>

          <div className="space-y-3">
            {settlements.map(s => (
              <Card key={s.id}>
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold capitalize">{s.offer_type.replace(/_/g, ' ')}</span>
                      <Badge variant={
                        s.status === 'accepted' ? 'success' :
                        s.status === 'rejected' || s.status === 'expired' ? 'danger' :
                        s.status === 'approved' ? 'info' :
                        s.status === 'needs_approval' ? 'warning' : 'info'
                      }>
                        {s.status}
                      </Badge>
                      {s.approval_required && s.status === 'draft' && (
                        <Badge variant="warning">Needs Approval</Badge>
                      )}
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-2 text-sm">
                      <div>
                        <span className="text-[var(--color-text-muted)] text-xs">Original</span>
                        <p>{fmt(s.original_balance)}</p>
                      </div>
                      <div>
                        <span className="text-[var(--color-text-muted)] text-xs">Settlement</span>
                        <p className="font-semibold text-emerald-400">{fmt(s.settlement_amount)}</p>
                      </div>
                      {s.discount_pct > 0 && (
                        <div>
                          <span className="text-[var(--color-text-muted)] text-xs">Discount</span>
                          <p>{s.discount_pct}%</p>
                        </div>
                      )}
                      {s.plan_months && (
                        <div>
                          <span className="text-[var(--color-text-muted)] text-xs">Plan</span>
                          <p>{s.plan_months}mo × {fmt(s.plan_monthly_amount)}</p>
                        </div>
                      )}
                      {s.lump_sum && (
                        <div>
                          <span className="text-[var(--color-text-muted)] text-xs">Lump Sum</span>
                          <p>{fmt(s.lump_sum)}</p>
                        </div>
                      )}
                    </div>
                    <p className="text-xs text-[var(--color-text-muted)] mt-2">
                      Offered by {s.offered_by_name} on {new Date(s.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex gap-1">
                    {s.approval_required && s.status === 'draft' && (
                      <button onClick={() => handleApproveSettlement(s.id)}
                        className="px-2 py-1 text-xs rounded bg-blue-500/20 text-blue-400 hover:bg-blue-500/30">
                        Approve
                      </button>
                    )}
                    {(s.status === 'approved' || (s.status === 'draft' && !s.approval_required)) && (
                      <button onClick={() => handleAcceptSettlement(s.id)}
                        className="px-2 py-1 text-xs rounded bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30">
                        Accept
                      </button>
                    )}
                  </div>
                </div>
              </Card>
            ))}
            {settlements.length === 0 && (
              <div className="text-center text-[var(--color-text-muted)] py-8">
                No settlement offers. Click "Calculate Options" to generate offers.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Compliance ─── */}
      {tab === 'compliance' && (
        <div className="space-y-4">
          <Card>
            <h3 className="font-semibold mb-4 flex items-center gap-2"><Scale size={16} /> Contact Compliance</h3>
            {compliance ? (
              <div>
                <div className={`flex items-center gap-2 text-lg font-bold mb-4 ${compliance.allowed ? 'text-emerald-400' : 'text-red-400'}`}>
                  {compliance.allowed ? <CheckCircle size={20} /> : <XCircle size={20} />}
                  {compliance.allowed ? 'Contact Permitted' : 'Contact Restricted'}
                </div>
                {compliance.reasons.length > 0 && (
                  <div className="space-y-2 mb-4">
                    {compliance.reasons.map((r, i) => (
                      <div key={i} className="flex items-start gap-2 p-2 rounded-lg bg-red-500/10 border border-red-500/20">
                        <XCircle size={14} className="text-red-400 mt-0.5 shrink-0" />
                        <span className="text-sm">{r}</span>
                      </div>
                    ))}
                  </div>
                )}
                {compliance.next_allowed_at && (
                  <p className="text-sm text-[var(--color-text-muted)]">
                    <Clock size={14} className="inline mr-1" />
                    Next allowed contact: {new Date(compliance.next_allowed_at).toLocaleString()}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-[var(--color-text-muted)]">No compliance rules configured for this jurisdiction.</p>
            )}
          </Card>

          <Card>
            <h3 className="font-semibold mb-3">Contact History Today</h3>
            <p className="text-sm text-[var(--color-text-muted)]">
              {records.filter(r => new Date(r.created_at).toDateString() === new Date().toDateString()).length} contacts today
            </p>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">
              {records.length} total interactions recorded
            </p>
          </Card>
        </div>
      )}
    </div>
  );
}
