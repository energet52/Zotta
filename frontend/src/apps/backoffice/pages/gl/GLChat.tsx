import { useState, useRef, useEffect } from 'react';
import { MessageSquare, Send, Loader2, ChevronDown, ChevronRight } from 'lucide-react';
import Card from '../../../../components/ui/Card';
import { glApi, type GLQueryResponse } from '../../../../api/glApi';

/* ── types ───────────────────────────────────── */

interface UserMessage {
  role: 'user';
  content: string;
  id: string;
}

interface AIMessage {
  role: 'assistant';
  content: GLQueryResponse;
  id: string;
}

type ChatMessage = UserMessage | AIMessage;

const EXAMPLE_QUESTIONS = [
  'What is the balance of Performing Loans?',
  'How many entries are posted?',
  'Show net income',
  'Show the trial balance',
  'List all disbursement entries',
  'Show top 10 entries',
];

/* ── Response renderers ──────────────────────── */

function ResponseNumber({ r }: { r: Extract<GLQueryResponse, { type: 'number' }> }) {
  return (
    <div className="space-y-1">
      <p className="text-2xl font-bold font-mono text-[var(--color-primary)]">
        {r.formatted ?? (r.value != null ? String(r.value) : '—')}
      </p>
      {r.summary && <p className="text-sm text-[var(--color-text-muted)]">{r.summary}</p>}
    </div>
  );
}

function ResponseTable({ r }: { r: Extract<GLQueryResponse, { type: 'table' }> }) {
  const data = r.data ?? [];
  const columns = r.columns ?? (data.length ? Object.keys(data[0] as object) : []);

  return (
    <div className="space-y-2">
      {r.summary && <p className="text-sm text-[var(--color-text-muted)]">{r.summary}</p>}
      {columns.length > 0 && (
        <div className="rounded-lg border border-[var(--color-border)] overflow-hidden max-h-64 overflow-y-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[var(--color-surface-hover)]">
                {columns.map((col) => (
                  <th
                    key={col}
                    className="py-2 px-3 text-left font-medium text-[var(--color-text-muted)] text-xs uppercase tracking-wider"
                  >
                    {col.replace(/_/g, ' ')}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((row, i) => (
                <tr
                  key={i}
                  className="border-t border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]"
                >
                  {columns.map((col) => (
                    <td key={col} className="py-2 px-3 text-[var(--color-text)]">
                      {typeof (row as Record<string, unknown>)[col] === 'number'
                        ? Number((row as Record<string, unknown>)[col]).toLocaleString('en-US', {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })
                        : String((row as Record<string, unknown>)[col] ?? '—')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ResponseSuggestion({ r }: { r: Extract<GLQueryResponse, { type: 'suggestion' }> }) {
  return (
    <p className="text-sm text-[var(--color-text-muted)] whitespace-pre-wrap">{r.message ?? 'Try asking a question.'}</p>
  );
}

function ResponseError({ r }: { r: Extract<GLQueryResponse, { type: 'error' }> }) {
  return <p className="text-sm text-[var(--color-danger)]">{r.message ?? 'An error occurred.'}</p>;
}

function QueryUsed({ queryUsed }: { queryUsed?: string | null }) {
  const [open, setOpen] = useState(false);
  if (!queryUsed) return null;
  return (
    <div className="mt-2 border-t border-[var(--color-border)] pt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-primary)]"
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        Show query
      </button>
      {open && (
        <pre className="mt-1 p-2 text-xs rounded bg-[var(--color-bg)] text-[var(--color-text-muted)] overflow-x-auto">
          {queryUsed}
        </pre>
      )}
    </div>
  );
}

function AIMessageContent({ response }: { response: GLQueryResponse }) {
  const queryUsed =
    'query_used' in response ? response.query_used : undefined;

  return (
    <div className="space-y-1">
      {response.type === 'number' && <ResponseNumber r={response} />}
      {response.type === 'table' && <ResponseTable r={response} />}
      {response.type === 'suggestion' && <ResponseSuggestion r={response} />}
      {response.type === 'error' && <ResponseError r={response} />}
      <QueryUsed queryUsed={queryUsed} />
    </div>
  );
}

/* ── main page ───────────────────────────────── */

export default function GLChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (question: string) => {
    const text = question.trim();
    if (!text || loading) return;
    setInput('');
    const userMsg: UserMessage = {
      role: 'user',
      content: text,
      id: `u-${Date.now()}`,
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    try {
      const { data } = await glApi.postQuery({ question: text });
      const aiMsg: AIMessage = {
        role: 'assistant',
        content: data,
        id: `a-${Date.now()}`,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch {
      const aiMsg: AIMessage = {
        role: 'assistant',
        content: { type: 'error', message: 'Failed to get response. Please try again.' },
        id: `a-${Date.now()}`,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSend(input);
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2.5 rounded-xl bg-[var(--color-primary)]/10">
          <MessageSquare size={22} className="text-[var(--color-primary)]" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">GL Chat</h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            Ask natural language questions about your General Ledger
          </p>
        </div>
      </div>

      <Card padding="none" className="flex flex-col overflow-hidden">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-[320px] max-h-[480px]">
          {messages.length === 0 && !loading && (
            <div className="text-center py-8">
              <p className="text-[var(--color-text-muted)] text-sm mb-4">
                Ask a question about your GL data. Try one of these:
              </p>
              <div className="flex flex-wrap gap-2 justify-center">
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => handleSend(q)}
                    className="px-3 py-1.5 text-xs rounded-full bg-[var(--color-surface-hover)] text-[var(--color-text)] hover:bg-[var(--color-primary)]/20 hover:text-[var(--color-primary)] transition-colors border border-[var(--color-border)]"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) => (
            <div
              key={m.id}
              className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[90%] rounded-xl px-4 py-3 text-sm ${
                  m.role === 'user'
                    ? 'bg-[var(--color-primary)] text-white rounded-br-md'
                    : 'bg-[var(--color-surface-hover)] border border-[var(--color-border)] text-[var(--color-text)] rounded-bl-md'
                }`}
              >
                {m.role === 'user' ? (
                  <p className="whitespace-pre-wrap">{m.content}</p>
                ) : (
                  <AIMessageContent response={m.content} />
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="rounded-xl px-4 py-3 bg-[var(--color-surface-hover)] border border-[var(--color-border)]">
                <Loader2 size={18} className="animate-spin text-[var(--color-primary)]" />
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Example chips above input */}
        <div className="px-4 pb-2 flex flex-wrap gap-1.5">
          {EXAMPLE_QUESTIONS.slice(0, 4).map((q) => (
            <button
              key={q}
              onClick={() => handleSend(q)}
              disabled={loading}
              className="px-2.5 py-1 text-xs rounded-lg bg-transparent text-[var(--color-text-muted)] hover:text-[var(--color-primary)] hover:bg-[var(--color-primary)]/10 transition-colors disabled:opacity-50"
            >
              {q.length > 35 ? q.slice(0, 35) + '…' : q}
            </button>
          ))}
        </div>

        {/* Input */}
        <form
          onSubmit={handleSubmit}
          className="border-t border-[var(--color-border)] p-4"
        >
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a GL question..."
              className="flex-1 px-4 py-2.5 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50 focus:border-[var(--color-primary)]"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="p-2.5 bg-[var(--color-primary)] text-white rounded-lg hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center"
            >
              {loading ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Send size={18} />
              )}
            </button>
          </div>
        </form>
      </Card>
    </div>
  );
}
