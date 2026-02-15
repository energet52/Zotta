import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { MessageCircle, ArrowRight } from 'lucide-react';
import Card from '../../../components/ui/Card';
import { conversationsApi } from '../../../api/endpoints';

interface Conversation {
  id: number;
  channel: string;
  current_state: string;
  loan_application_id: number | null;
  escalated_at: string | null;
  escalation_reason: string | null;
  created_at: string;
  last_activity_at: string;
}

const STATE_LABELS: Record<string, string> = {
  initiated: 'Initiated',
  discovery: 'Discovery',
  application_in_progress: 'Application',
  documents_pending: 'Documents',
  verification_in_progress: 'Verification',
  credit_check_consent: 'Credit Consent',
  credit_check_in_progress: 'Credit Check',
  decision_rendered: 'Decision',
  offer_presented: 'Offer',
  offer_accepted: 'Accepted',
  disbursement_processing: 'Disbursing',
  disbursed: 'Disbursed',
  declined: 'Declined',
  withdrawn: 'Withdrawn',
  expired: 'Expired',
  escalated_to_human: 'Escalated',
  servicing: 'Servicing',
};

export default function ConversationQueue() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('active');

  useEffect(() => {
    conversationsApi.list(filter === 'all' ? undefined : filter)
      .then((res) => setConversations(res.data))
      .catch(() => setConversations([]))
      .finally(() => setLoading(false));
  }, [filter]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-[var(--color-text-muted)]">Loading conversations...</div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">Conversations</h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            Customer Support chat queue – monitor and take over when needed
          </p>
        </div>
      </div>

      <div className="flex gap-2 mb-4">
        {['active', 'escalated', 'all'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              filter === f
                ? 'bg-[var(--color-primary)] text-white'
                : 'bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] border border-[var(--color-border)]'
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      <Card padding="none">
        {conversations.length === 0 ? (
          <div className="p-12 text-center text-[var(--color-text-muted)]">
            No conversations found.
          </div>
        ) : (
          <div className="divide-y divide-[var(--color-border)]">
            {conversations.map((c) => (
              <Link
                key={c.id}
                to={`/backoffice/conversations/${c.id}`}
                className="flex items-center justify-between p-4 hover:bg-[var(--color-surface-hover)] transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-[var(--color-primary)]/20 flex items-center justify-center">
                    <MessageCircle size={20} className="text-[var(--color-primary)]" />
                  </div>
                  <div>
                    <p className="font-medium text-[var(--color-text)]">
                      Conversation #{c.id}
                      {c.loan_application_id && (
                        <span className="text-[var(--color-text-muted)] font-normal ml-2">
                          (App #{c.loan_application_id})
                        </span>
                      )}
                    </p>
                    <p className="text-sm text-[var(--color-text-muted)]">
                      {STATE_LABELS[c.current_state] || c.current_state} · {c.channel}
                    </p>
                    {c.escalated_at && (
                      <p className="text-xs text-amber-500 mt-0.5">
                        Escalated{c.escalation_reason ? `: ${c.escalation_reason}` : ''}
                      </p>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-xs text-[var(--color-text-muted)]">
                    {new Date(c.last_activity_at).toLocaleString()}
                  </p>
                  <ArrowRight size={16} className="ml-2 mt-1 opacity-50" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
