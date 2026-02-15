import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, MessageCircle, FileText } from 'lucide-react';
import Card from '../../../components/ui/Card';
import { conversationsApi } from '../../../api/endpoints';

interface Message {
  id: number;
  role: string;
  content: string;
  created_at: string;
  metadata?: Record<string, unknown>;
}

interface ConversationDetail {
  id: number;
  channel: string;
  current_state: string;
  loan_application_id: number | null;
  entry_point: string | null;
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

  useEffect(() => {
    if (!id) return;
    conversationsApi.get(parseInt(id, 10))
      .then((res) => setConv(res.data))
      .catch(() => setConv(null))
      .finally(() => setLoading(false));
  }, [id]);

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
        <div className="lg:col-span-2">
          <Card>
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
            <div className="space-y-3 max-h-[500px] overflow-y-auto">
              {conv.messages.map((m) => (
                <div
                  key={m.id}
                  className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] rounded-lg px-4 py-2 text-sm ${
                      m.role === 'user'
                        ? 'bg-[var(--color-primary)] text-white rounded-br-none'
                        : 'bg-[var(--color-surface-hover)] border border-[var(--color-border)] text-[var(--color-text)] rounded-bl-none'
                    }`}
                  >
                    {m.role !== 'user' && (
                      <p className="text-[10px] font-semibold mb-0.5 opacity-70">
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
            </div>
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
