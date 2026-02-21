import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bell, MessageSquare, CheckCheck, ArrowRight, MessageCircle } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { useNotificationStore } from '../../../store/notificationStore';
import { loanApi } from '../../../api/endpoints';
import type { Notification } from '../../../store/notificationStore';

interface CollectionMessage {
  id: number;
  application_id: number;
  reference_number: string;
  direction: string;
  message: string;
  channel: string;
  status: string;
  created_at: string;
}

export default function Notifications() {
  const { notifications, unreadCount, fetch, markAllRead } = useNotificationStore();
  const [collectionMessages, setCollectionMessages] = useState<CollectionMessage[]>([]);

  useEffect(() => {
    fetch();
    loadCollectionMessages();
  }, []);

  const loadCollectionMessages = async () => {
    try {
      const res = await loanApi.getCollectionMessages();
      setCollectionMessages(res.data.messages || []);
    } catch { /* ignore */ }
  };

  // Group notifications by application
  const grouped = notifications.reduce<Record<number, { reference: string; items: Notification[] }>>((acc, n) => {
    if (!acc[n.application_id]) {
      acc[n.application_id] = { reference: n.reference_number, items: [] };
    }
    acc[n.application_id].items.push(n);
    return acc;
  }, {});

  const groupedEntries = Object.entries(grouped).sort((a, b) => {
    // Sort by most recent message in each group
    const aLatest = a[1].items[0]?.created_at || '';
    const bLatest = b[1].items[0]?.created_at || '';
    return bLatest.localeCompare(aLatest);
  });

  // Group collection messages by application
  const collectionGrouped = collectionMessages.reduce<Record<number, { reference: string; items: CollectionMessage[] }>>((acc, m) => {
    if (!acc[m.application_id]) {
      acc[m.application_id] = { reference: m.reference_number, items: [] };
    }
    acc[m.application_id].items.push(m);
    return acc;
  }, {});

  const collectionEntries = Object.entries(collectionGrouped).sort((a, b) => {
    const aLatest = a[1].items[0]?.created_at || '';
    const bLatest = b[1].items[0]?.created_at || '';
    return bLatest.localeCompare(aLatest);
  });

  const hasNotifications = groupedEntries.length > 0;
  const hasCollectionMessages = collectionEntries.length > 0;
  const hasAnything = hasNotifications || hasCollectionMessages;

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <Bell size={24} className="text-[var(--color-primary)]" />
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-text)]">Notifications</h1>
            <p className="text-sm text-[var(--color-text-muted)]">
              {unreadCount > 0
                ? `You have ${unreadCount} unread message${unreadCount !== 1 ? 's' : ''}`
                : 'All caught up!'}
            </p>
          </div>
        </div>
        {unreadCount > 0 && (
          <Button size="sm" variant="ghost" onClick={markAllRead}>
            <CheckCheck size={14} className="mr-1" /> Mark all read
          </Button>
        )}
      </div>

      {/* Collection Messages Section */}
      {hasCollectionMessages && (
        <div className="mb-6">
          <div className="flex items-center space-x-2 mb-3">
            <MessageCircle size={18} className="text-emerald-400" />
            <h2 className="text-lg font-semibold text-[var(--color-text)]">Collection Messages</h2>
          </div>
          <div className="space-y-4">
            {collectionEntries.map(([appId, group]) => (
              <Card key={`col-${appId}`}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center space-x-2">
                    <MessageCircle size={16} className="text-emerald-400" />
                    <h3 className="font-semibold text-[var(--color-text)]">
                      Loan {group.reference}
                    </h3>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 font-medium">
                      WhatsApp
                    </span>
                  </div>
                  <Link
                    to={`/applications/${appId}`}
                    className="flex items-center text-sm text-[var(--color-primary)] hover:underline"
                  >
                    View Loan <ArrowRight size={14} className="ml-1" />
                  </Link>
                </div>
                <div className="space-y-2">
                  {group.items.slice(0, 5).map((m) => (
                    <div
                      key={`col-msg-${m.id}`}
                      className={`p-3 rounded-lg border border-[var(--color-border)] ${
                        m.direction === 'outbound'
                          ? 'bg-emerald-500/5 border-emerald-500/20'
                          : 'bg-[var(--color-bg)]'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center space-x-2 mb-1">
                            <span className="text-xs font-semibold text-[var(--color-text-muted)]">
                              {m.direction === 'outbound' ? 'Collections Team' : 'You'}
                            </span>
                            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                              m.direction === 'outbound'
                                ? 'bg-emerald-500/15 text-emerald-400'
                                : 'bg-blue-500/15 text-blue-400'
                            }`}>
                              {m.direction === 'outbound' ? 'from lender' : 'your reply'}
                            </span>
                          </div>
                          <p className="text-sm text-[var(--color-text)] line-clamp-3">{m.message}</p>
                        </div>
                        <span className="text-[10px] text-[var(--color-text-muted)] ml-3 shrink-0 mt-0.5">
                          {m.created_at ? formatTimeAgo(m.created_at) : ''}
                        </span>
                      </div>
                    </div>
                  ))}
                  {group.items.length > 5 && (
                    <div className="text-center text-xs text-[var(--color-text-muted)] py-1">
                      +{group.items.length - 5} more messages
                    </div>
                  )}
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Underwriter Messages Section */}
      {hasNotifications && (
        <div>
          {hasCollectionMessages && (
            <div className="flex items-center space-x-2 mb-3">
              <MessageSquare size={18} className="text-[var(--color-primary)]" />
              <h2 className="text-lg font-semibold text-[var(--color-text)]">Application Messages</h2>
            </div>
          )}
          <div className="space-y-4">
            {groupedEntries.map(([appId, group]) => {
              const unreadInGroup = group.items.filter((n) => !n.read).length;
              return (
                <Card key={appId}>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center space-x-2">
                      <MessageSquare size={16} className="text-[var(--color-primary)]" />
                      <h3 className="font-semibold text-[var(--color-text)]">
                        Application {group.reference}
                      </h3>
                      {unreadInGroup > 0 && (
                        <span className="min-w-0 sm:min-w-[20px] h-[20px] flex items-center justify-center rounded-full bg-red-500 text-white text-[10px] font-bold px-1">
                          {unreadInGroup}
                        </span>
                      )}
                    </div>
                    <Link
                      to={`/applications/${appId}`}
                      className="flex items-center text-sm text-[var(--color-primary)] hover:underline"
                    >
                      View & Reply <ArrowRight size={14} className="ml-1" />
                    </Link>
                  </div>

                  <div className="space-y-2">
                    {group.items.slice(0, 5).map((n) => (
                      <Link
                        key={n.id}
                        to={`/applications/${n.application_id}`}
                        className={`block p-3 rounded-lg border transition-colors ${
                          n.read
                            ? 'border-[var(--color-border)] bg-[var(--color-bg)]'
                            : 'border-[var(--color-primary)]/30 bg-[var(--color-primary)]/5'
                        } hover:bg-[var(--color-surface-hover)]`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center space-x-2 mb-1">
                              <span className="text-xs font-semibold text-[var(--color-text-muted)]">
                                {n.author_name}
                              </span>
                              {!n.read && (
                                <span className="w-2 h-2 rounded-full bg-[var(--color-primary)] shrink-0" />
                              )}
                            </div>
                            <p className="text-sm text-[var(--color-text)] line-clamp-2">{n.content}</p>
                          </div>
                          <span className="text-[10px] text-[var(--color-text-muted)] ml-3 shrink-0 mt-0.5">
                            {n.created_at ? formatTimeAgo(n.created_at) : ''}
                          </span>
                        </div>
                      </Link>
                    ))}
                    {group.items.length > 5 && (
                      <Link
                        to={`/applications/${appId}`}
                        className="block text-center text-xs text-[var(--color-primary)] hover:underline py-1"
                      >
                        +{group.items.length - 5} more messages
                      </Link>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!hasAnything && (
        <Card>
          <div className="text-center py-12">
            <Bell size={40} className="mx-auto mb-3 text-[var(--color-text-muted)] opacity-30" />
            <p className="text-[var(--color-text-muted)]">No messages yet</p>
            <p className="text-xs text-[var(--color-text-muted)] mt-1">
              When a staff member sends you a message, you&apos;ll see it here.
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}

function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHrs = Math.floor(diffMins / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;
  const diffDays = Math.floor(diffHrs / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}
