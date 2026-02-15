import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, MessageCircle } from 'lucide-react';
import Card from '../../../components/ui/Card';
import ChatWindow from '../../../components/ChatWindow';
import { conversationsApi } from '../../../api/endpoints';

const STORAGE_KEY = 'zotta_conversation_id';

interface Message {
  id: number;
  role: string;
  content: string;
  created_at: string;
}

export default function Chat() {
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [initLoading, setInitLoading] = useState(true);

  const loadOrCreate = useCallback(async () => {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (stored) {
      const id = parseInt(stored, 10);
      if (!isNaN(id)) {
        try {
          const res = await conversationsApi.get(id);
          setConversationId(id);
          setMessages(res.data.messages || []);
          setLoading(false);
          setInitLoading(false);
          return;
        } catch {
          sessionStorage.removeItem(STORAGE_KEY);
        }
      }
    }
    try {
      const res = await conversationsApi.create();
      const id = res.data.id;
      setConversationId(id);
      setMessages(res.data.messages || []);
      sessionStorage.setItem(STORAGE_KEY, String(id));
    } catch {
      setConversationId(null);
      setMessages([]);
    } finally {
      setLoading(false);
      setInitLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOrCreate();
  }, [loadOrCreate]);

  const handleSend = async (content: string) => {
    if (!conversationId) return;
    const userMsg: Message = {
      id: -Date.now(),
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    try {
      const res = await conversationsApi.sendMessage(conversationId, content);
      const assistantMsg: Message = {
        id: res.data.id,
        role: res.data.role,
        content: res.data.content,
        created_at: res.data.created_at,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } finally {
      setLoading(false);
    }
  };

  if (initLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-[var(--color-text-muted)]">Loading chat...</div>
      </div>
    );
  }

  if (!conversationId) {
    return (
      <div className="max-w-2xl mx-auto">
        <Card>
          <p className="text-[var(--color-text-muted)]">
            Unable to start a conversation. Please try again or{' '}
            <Link to="/login" className="text-[var(--color-primary)] hover:underline">
              log in
            </Link>{' '}
            for a better experience.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center gap-3 mb-4">
        <Link
          to="/dashboard"
          className="inline-flex items-center text-sm text-[var(--color-text-muted)] hover:text-[var(--color-primary)] transition-colors"
        >
          <ArrowLeft size={18} className="mr-1" />
          Back to Dashboard
        </Link>
      </div>

      <div className="flex items-center gap-2 mb-4">
        <div className="w-10 h-10 rounded-lg bg-[var(--color-primary)]/20 flex items-center justify-center">
          <MessageCircle size={20} className="text-[var(--color-primary)]" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-[var(--color-text)]">Chat with Zotta</h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            Customer Support. Ask about your balance, payments, loans, or apply.
          </p>
        </div>
      </div>

      <ChatWindow
        conversationId={conversationId}
        messages={messages}
        onSend={handleSend}
        loading={loading}
      />
    </div>
  );
}
