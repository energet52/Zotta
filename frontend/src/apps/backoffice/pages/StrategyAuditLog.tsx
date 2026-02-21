import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  ScrollText,
  Shield,
  ClipboardCheck,
  GitBranch,
  Clock,
  ChevronRight,
  Search,
} from 'lucide-react';
import api from '../../../api/client';

interface TimelineEntry {
  type: string;
  action: string;
  entity_id: number;
  entity_name: string;
  description: string;
  details: Record<string, unknown>;
  timestamp: string;
}

interface AuditData {
  timeline: TimelineEntry[];
  total_strategies: number;
}

const typeIcons: Record<string, typeof Shield> = {
  strategy: Shield,
  assessment: ClipboardCheck,
  decision_tree: GitBranch,
};

const typeColors: Record<string, string> = {
  strategy: 'text-blue-500 bg-blue-500/10',
  assessment: 'text-orange-500 bg-orange-500/10',
  decision_tree: 'text-purple-500 bg-purple-500/10',
};

const actionColors: Record<string, string> = {
  active: 'text-emerald-500 bg-emerald-500/10',
  draft: 'text-gray-400 bg-gray-400/10',
  archived: 'text-gray-500 bg-gray-500/10',
  created: 'text-blue-500 bg-blue-500/10',
  configured: 'text-orange-500 bg-orange-500/10',
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
    ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

export default function StrategyAuditLog() {
  const [search, setSearch] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['strategy-audit-log'],
    queryFn: async () => {
      const res = await api.get('/strategy-audit-log?limit=100');
      return res.data as AuditData;
    },
  });

  const timeline = (data?.timeline || []).filter((entry) =>
    !search ||
    entry.entity_name.toLowerCase().includes(search.toLowerCase()) ||
    entry.description.toLowerCase().includes(search.toLowerCase()) ||
    entry.type.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-[var(--color-text)]">Strategy Audit Log</h1>
          <p className="text-sm text-[var(--color-text-secondary)] mt-1">
            History of changes across all strategies and assessments
            {data && <span className="ml-2">({data.total_strategies} strategies)</span>}
          </p>
        </div>
      </div>

      <div className="relative mb-4">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-secondary)]" />
        <input
          type="text"
          placeholder="Search by strategy or assessment name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-blue-500/30"
        />
      </div>

      {isLoading && (
        <div className="text-center py-8 text-sm text-[var(--color-text-secondary)]">Loading...</div>
      )}

      {!isLoading && timeline.length === 0 && (
        <div className="text-center py-12">
          <ScrollText size={40} className="mx-auto mb-3 text-[var(--color-text-secondary)]" />
          <p className="text-sm text-[var(--color-text)]">No audit entries found</p>
        </div>
      )}

      <div className="relative">
        <div className="absolute left-5 top-0 bottom-0 w-px bg-[var(--color-border)]" />

        {timeline.map((entry, i) => {
          const Icon = typeIcons[entry.type] || Shield;
          const color = typeColors[entry.type] || 'text-gray-400 bg-gray-400/10';
          const actionColor = actionColors[entry.action] || 'text-gray-400 bg-gray-400/10';
          const details = entry.details || {};

          return (
            <div key={`${entry.type}-${entry.entity_id}-${i}`} className="relative pl-12 pb-4">
              <div className={`absolute left-3 w-5 h-5 rounded-full flex items-center justify-center ${color}`}>
                <Icon size={11} />
              </div>

              <div
                className="rounded-lg border px-4 py-3"
                style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm text-[var(--color-text)]">
                      {entry.entity_name}
                    </span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${actionColor}`}>
                      {entry.action}
                    </span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${color}`}>
                      {entry.type}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 text-xs text-[var(--color-text-secondary)]">
                    <Clock size={10} />
                    {formatDate(entry.timestamp)}
                  </div>
                </div>

                <p className="text-xs text-[var(--color-text-secondary)]">{entry.description}</p>

                {entry.type === 'strategy' && (
                  <div className="flex items-center gap-3 mt-2 text-xs text-[var(--color-text-secondary)]">
                    <span>v{String(details.version || 1)}</span>
                    {details.assessments !== undefined && <span>{String(details.assessments)} assessments</span>}
                    {Boolean(details.has_tree) && <span>has tree</span>}
                    {Boolean(details.is_fallback) && <span className="text-gray-400">fallback</span>}
                    <Link
                      to="/backoffice/strategies"
                      className="flex items-center gap-0.5 text-blue-500 hover:text-blue-400"
                    >
                      View <ChevronRight size={10} />
                    </Link>
                  </div>
                )}

                {entry.type === 'assessment' && (
                  <div className="flex items-center gap-3 mt-2 text-xs text-[var(--color-text-secondary)]">
                    <span>{String(details.rule_count || 0)} rules</span>
                    <span>on {String(details.strategy_name || '?')}</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
