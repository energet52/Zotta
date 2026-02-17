import { useEffect, useRef, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, MessageCircle, FileText, Send, Loader2 } from 'lucide-react';
import Card from '../../../components/ui/Card';
import { conversationsApi, customerApi } from '../../../api/endpoints';

interface Message {
  id: number;
  role: string;
  content: string;
  created_at: string;
  metadata?: Record<string, unknown>;
}

interface ConversationDetail {
  id: number;
  participant_user_id: number | null;
  channel: string;
  current_state: string;
  loan_application_id: number | null;
  entry_point: string | null;
  assigned_agent_id: number | null;
  escalated_at: string | null;
  escalation_reason: string | null;
  created_at: string;
  last_activity_at: string;
  messages: Message[];
  application_summary?: {
    id: number;
    reference_number: string;
    status: string;
    amount_requested: number;
    term_months: number;
  };
}

export default function ConversationDetail() {
  const { id } = useParams<{ id: string }>();
  const [conv, setConv] = useState<ConversationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const fetchConversation = (conversationId: number) => {
    return conversationsApi
      .get(conversationId)
      .then((res) => setConv(res.data))
      .catch(() => setConv(null));
  };

  useEffect(() => {
    if (!id) return;
    fetchConversation(parseInt(id, 10)).finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conv?.messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending || !conv || !conv.participant_user_id) return;

    setInput('');
    setSending(true);
    try {
      await customerApi.staffSendMessage(conv.participant_user_id, conv.id, text);
      await fetchConversation(conv.id);
    } catch {
      // restore input on failure so the agent doesn't lose their message
      setInput(text);
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-[var(--color-text-muted)]">Loading...</div>
      </div>
    );
  }

  if (!conv) {
    return (
      <div className="text-center py-12 text-[var(--color-danger)]">
        Conversation not found.
      </div>
    );
  }

  const canReply = !!conv.participant_user_id;

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Link
          to="/backoffice/conversations"
          className="inline-flex items-center text-sm text-[var(--color-text-muted)] hover:text-[var(--color-primary)] transition-colors"
        >
          <ArrowLeft size={18} className="mr-1" />
          Back to Queue
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 flex flex-col">
          <Card className="flex-1 flex flex-col">
            <h2 className="font-semibold text-[var(--color-text)] mb-4 flex items-center">
              <MessageCircle size={18} className="mr-2 text-[var(--color-primary)]" />
              Conversation #{conv.id}
            </h2>
            <p className="text-sm text-[var(--color-text-muted)] mb-4">
              State: <span className="font-medium text-[var(--color-text)]">{conv.current_state}</span>
              {conv.escalation_reason && (
                <span className="ml-2 text-amber-500"> · Escalated: {conv.escalation_reason}</span>
              )}
            </p>

            {/* Messages */}
            <div className="flex-1 space-y-3 max-h-[450px] overflow-y-auto mb-4">
              {conv.messages.map((m) => (
                <div
                  key={m.id}
                  className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] rounded-lg px-4 py-2 text-sm ${
                      m.role === 'user'
                        ? 'bg-[var(--color-primary)] text-white rounded-br-none'
                        : m.role === 'agent'
                          ? 'bg-emerald-50 dark:bg-emerald-900/30 border border-emerald-200 dark:border-emerald-800 text-[var(--color-text)] rounded-bl-none'
                          : 'bg-[var(--color-surface-hover)] border border-[var(--color-border)] text-[var(--color-text)] rounded-bl-none'
                    }`}
                  >
                    {m.role !== 'user' && (
                      <p className={`text-[10px] font-semibold mb-0.5 ${
                        m.role === 'agent' ? 'text-emerald-600 dark:text-emerald-400' : 'opacity-70'
                      }`}>
                        {m.role === 'agent' ? 'Agent' : 'Zotta AI'}
                      </p>
                    )}
                    <p className="whitespace-pre-wrap">{m.content}</p>
                    <p className={`text-[10px] mt-1 ${m.role === 'user' ? 'text-white/70' : 'text-[var(--color-text-muted)]'}`}>
                      {new Date(m.created_at).toLocaleString()}
                    </p>
                    {m.metadata?.intent !== undefined && m.metadata?.intent !== null && (
                      <p className="text-[10px] mt-1 italic opacity-70">
                        Intent: {String(m.metadata.intent)}
                      </p>
                    )}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* Agent reply input */}
            {canReply ? (
              <form onSubmit={handleSend} className="border-t border-[var(--color-border)] pt-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Type your reply to the customer..."
                    className="flex-1 px-4 py-2.5 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50 focus:border-[var(--color-primary)]"
                    disabled={sending}
                  />
                  <button
                    type="submit"
                    disabled={sending || !input.trim()}
                    className="p-2.5 bg-[var(--color-primary)] text-white rounded-lg hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center"
                  >
                    {sending ? (
                      <Loader2 size={18} className="animate-spin" />
                    ) : (
                      <Send size={18} />
                    )}
                  </button>
                </div>
              </form>
            ) : (
              <p className="text-xs text-[var(--color-text-muted)] border-t border-[var(--color-border)] pt-3">
                Anonymous conversation — replies are not available.
              </p>
            )}
          </Card>
        </div>

        <div>
          <Card>
            <h3 className="font-semibold text-[var(--color-text)] mb-4">Summary</h3>
            <dl className="space-y-2 text-sm">
              <dt className="text-[var(--color-text-muted)]">Channel</dt>
              <dd className="text-[var(--color-text)]">{conv.channel}</dd>
              <dt className="text-[var(--color-text-muted)]">State</dt>
              <dd className="text-[var(--color-text)]">{conv.current_state}</dd>
              <dt className="text-[var(--color-text-muted)]">Created</dt>
              <dd className="text-[var(--color-text)]">{new Date(conv.created_at).toLocaleString()}</dd>
              <dt className="text-[var(--color-text-muted)]">Last activity</dt>
              <dd className="text-[var(--color-text)]">{new Date(conv.last_activity_at).toLocaleString()}</dd>
            </dl>

            {conv.application_summary && (
              <div className="mt-4 pt-4 border-t border-[var(--color-border)]">
                <h4 className="font-semibold text-[var(--color-text)] mb-2 flex items-center">
                  <FileText size={14} className="mr-2" />
                  Linked Application
                </h4>
                <Link
                  to={`/backoffice/review/${conv.application_summary.id}`}
                  className="text-[var(--color-primary)] hover:underline"
                >
                  {conv.application_summary.reference_number}
                </Link>
                <p className="text-sm text-[var(--color-text-muted)] mt-1">
                  TTD {conv.application_summary.amount_requested.toLocaleString()} · {conv.application_summary.term_months} months · {conv.application_summary.status}
                </p>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
