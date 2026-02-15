import { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, MessageCircle, Phone, Mail, Send, Plus, User
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

export default function CollectionDetail() {
  const { id } = useParams<{ id: string }>();
  const appId = parseInt(id || '0');
  const [app, setApp] = useState<any>(null);
  const [records, setRecords] = useState<CollectionRecord[]>([]);
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'history' | 'chat'>('history');
  const [showForm, setShowForm] = useState(false);
  const [chatMsg, setChatMsg] = useState('');
  const [sendingChat, setSendingChat] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Form state
  const [form, setForm] = useState({
    channel: 'phone',
    notes: '',
    action_taken: '',
    outcome: 'no_answer',
    next_action_date: '',
    promise_amount: '',
    promise_date: '',
  });

  useEffect(() => {
    loadData();
  }, [appId]);

  // Poll for new chat messages every 4 seconds when the chat tab is active
  useEffect(() => {
    if (tab !== 'chat') return;
    const interval = setInterval(async () => {
      try {
        const chatRes = await collectionsApi.getChat(appId);
        setChat(chatRes.data);
      } catch { /* ignore */ }
    }, 4000);
    return () => clearInterval(interval);
  }, [appId, tab]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chat]);

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

  const fmt = (val: number | null | undefined) =>
    val != null ? `TTD ${val.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '—';

  const inputClass = "w-full h-[38px] px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]";

  if (loading) return <div className="flex items-center justify-center h-64 text-[var(--color-text-muted)]">Loading...</div>;
  if (!app) return <div className="text-center text-[var(--color-text-muted)]">Application not found</div>;

  const application = app.application;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-3">
        <Link to="/backoffice/collections" className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
          <ArrowLeft size={20} />
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Collection: {application.reference_number}</h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            Loan: {fmt(application.amount_approved)} at {application.interest_rate}% for {application.term_months} months
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <div className="text-xs text-[var(--color-text-muted)]">Loan Amount</div>
          <div className="text-lg font-bold text-[var(--color-text)] mt-1">{fmt(application.amount_approved)}</div>
        </Card>
        <Card>
          <div className="text-xs text-[var(--color-text-muted)]">Monthly Payment</div>
          <div className="text-lg font-bold text-[var(--color-text)] mt-1">{fmt(application.monthly_payment)}</div>
        </Card>
        <Card>
          <div className="text-xs text-[var(--color-text-muted)]">Interactions</div>
          <div className="text-lg font-bold text-[var(--color-primary)] mt-1">{records.length}</div>
        </Card>
        <Card>
          <div className="text-xs text-[var(--color-text-muted)]">Status</div>
          <div className="text-lg font-bold text-[var(--color-danger)] mt-1 capitalize">{application.status.replace(/_/g, ' ')}</div>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex space-x-1 bg-[var(--color-surface)] rounded-lg p-1 w-fit">
        <button
          onClick={() => setTab('history')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            tab === 'history' ? 'bg-[var(--color-primary)] text-white' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
          }`}
        >
          Interaction History
        </button>
        <button
          onClick={() => setTab('chat')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            tab === 'chat' ? 'bg-[var(--color-primary)] text-white' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
          }`}
        >
          WhatsApp Chat
        </button>
      </div>

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

          {/* Timeline */}
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
                  <div className="text-xs text-[var(--color-text-muted)]">
                    {new Date(record.created_at).toLocaleString()}
                  </div>
                </div>
              </Card>
            ))}
            {records.length === 0 && (
              <div className="text-center text-[var(--color-text-muted)] py-8">No interactions recorded yet</div>
            )}
          </div>
        </div>
      )}

      {tab === 'chat' && (
        <Card className="flex flex-col" style={{ height: '500px' }}>
          {/* Chat Messages */}
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

          {/* Chat Input */}
          <div className="border-t border-[var(--color-border)] p-3 flex space-x-2">
            <input
              type="text"
              value={chatMsg}
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
    </div>
  );
}
