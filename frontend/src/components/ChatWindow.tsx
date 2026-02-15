import { useEffect, useRef, useState } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface Message {
  id: number;
  role: string;
  content: string;
  created_at: string;
}

interface ChatWindowProps {
  conversationId: number;
  messages: Message[];
  onSend: (content: string) => Promise<void>;
  loading?: boolean;
}

export default function ChatWindow({
  messages,
  onSend,
  loading = false,
}: ChatWindowProps) {
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;
    setInput('');
    setSending(true);
    try {
      await onSend(text);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex flex-col h-[500px] bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl overflow-hidden">
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && !loading && (
          <p className="text-center text-[var(--color-text-muted)] text-sm py-8">
            Start the conversation. Type a message below.
          </p>
        )}
        {messages.map((m) => (
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
              <p className="whitespace-pre-wrap">{m.content}</p>
              <p
                className={`text-[10px] mt-1 ${
                  m.role === 'user' ? 'text-white/70' : 'text-[var(--color-text-muted)]'
                }`}
              >
                {new Date(m.created_at).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </p>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="rounded-lg px-4 py-2 bg-[var(--color-surface-hover)] border border-[var(--color-border)]">
              <Loader2 size={16} className="animate-spin text-[var(--color-primary)]" />
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form onSubmit={handleSubmit} className="border-t border-[var(--color-border)] p-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
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
    </div>
  );
}
