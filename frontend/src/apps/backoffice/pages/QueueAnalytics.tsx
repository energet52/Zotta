import { useEffect, useState, useCallback } from 'react';
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Minus,
  Clock,
  Users,
  CheckCircle,
  AlertTriangle,
  Loader2,
  RefreshCw,
  Brain,
  Inbox,
  Sparkles,
  X,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { queueApi } from '../../../api/endpoints';

/* ── Types ─────────────────────────────────────────── */

interface AmbientData {
  pending: number;
  new_last_7d: number;
  decided_last_7d: number;
  avg_turnaround_hours?: number;
  trend: string;
}

interface ThroughputDay { date: string; count: number }
interface ThroughputData {
  period_days: number;
  submitted_by_day: ThroughputDay[];
  decided_by_day: ThroughputDay[];
}

interface TeamMember {
  user_id: number;
  name: string;
  decisions_30d: number;
  avg_turnaround_hours?: number;
}

interface Insight {
  type: string;
  title: string;
  description: string;
  metric?: number;
  severity?: string;
  unit?: string;
}

/* ── Helpers ───────────────────────────────────────── */

const trendIcon = (trend: string) => {
  if (trend === 'growing') return <TrendingUp size={14} className="text-red-400" />;
  if (trend === 'shrinking') return <TrendingDown size={14} className="text-green-400" />;
  return <Minus size={14} className="text-gray-400" />;
};

function insightIcon(severity?: string) {
  if (severity === 'warning') return <AlertTriangle size={16} className="text-amber-400" />;
  if (severity === 'info') return <Sparkles size={16} className="text-sky-400" />;
  return <Brain size={16} className="text-purple-400" />;
}

/* ── Component ─────────────────────────────────────── */

export default function QueueAnalytics() {
  const [ambient, setAmbient] = useState<AmbientData | null>(null);
  const [throughput, setThroughput] = useState<ThroughputData | null>(null);
  const [team, setTeam] = useState<TeamMember[]>([]);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [pipeline, setPipeline] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [ambRes, thrRes, teamRes, insRes, pipeRes] = await Promise.all([
        queueApi.getAmbientAnalytics(),
        queueApi.getThroughputAnalytics(30),
        queueApi.getTeamAnalytics(),
        queueApi.getInsights(),
        queueApi.getPipeline().catch(() => ({ data: null })),
      ]);
      setAmbient(ambRes.data);
      setThroughput(thrRes.data);
      setTeam(teamRes.data.team || []);
      setInsights(insRes.data.insights || []);
      setPipeline(pipeRes.data);
    } catch {
      setError('Failed to load analytics');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-[var(--color-text-muted)]">
      <Loader2 className="animate-spin mr-2" /> Loading analytics...
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2"><BarChart3 size={24} /> Queue Analytics</h1>
        <Button size="sm" variant="secondary" onClick={loadData}><RefreshCw size={14} className="mr-1" /> Refresh</Button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-2 rounded-lg text-sm flex items-center gap-2">
          <AlertTriangle size={14} /> {error}
          <button onClick={() => setError('')} className="ml-auto"><X size={12} /></button>
        </div>
      )}

      {/* ── KPI Cards ── */}
      {ambient && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[
            {
              label: 'Pending',
              value: ambient.pending,
              icon: <Inbox size={18} className="text-sky-400" />,
              sub: <span className="flex items-center gap-1 text-xs">{trendIcon(ambient.trend)} {ambient.trend}</span>,
            },
            {
              label: 'New (7d)',
              value: ambient.new_last_7d,
              icon: <TrendingUp size={18} className="text-green-400" />,
            },
            {
              label: 'Decided (7d)',
              value: ambient.decided_last_7d,
              icon: <CheckCircle size={18} className="text-emerald-400" />,
            },
            {
              label: 'Avg Turnaround',
              value: ambient.avg_turnaround_hours ? `${ambient.avg_turnaround_hours}h` : '-',
              icon: <Clock size={18} className="text-amber-400" />,
              sub: ambient.avg_turnaround_hours ? <span className="text-xs text-[var(--color-text-muted)]">{(ambient.avg_turnaround_hours / 24).toFixed(1)}d</span> : null,
            },
            {
              label: 'Net Flow (7d)',
              value: ambient.new_last_7d - ambient.decided_last_7d,
              icon: ambient.new_last_7d > ambient.decided_last_7d ? <TrendingUp size={18} className="text-red-400" /> : <TrendingDown size={18} className="text-green-400" />,
              sub: <span className="text-xs text-[var(--color-text-muted)]">in - out</span>,
            },
          ].map((kpi, i) => (
            <Card key={i}>
              <div className="flex items-center gap-2 mb-1">{kpi.icon}<span className="text-xs text-[var(--color-text-muted)]">{kpi.label}</span></div>
              <div className="text-2xl font-bold">{kpi.value}</div>
              {kpi.sub && <div className="mt-1">{kpi.sub}</div>}
            </Card>
          ))}
        </div>
      )}

      {/* ── Pipeline Funnel ── */}
      {pipeline && pipeline.stages && pipeline.stages.length > 0 && (
        <Card>
          <h3 className="text-sm font-medium mb-3 flex items-center gap-1.5">
            <BarChart3 size={14} className="text-sky-400" /> Pipeline
          </h3>
          <div className="flex items-end gap-2 overflow-x-auto pb-2">
            {/* Unassigned */}
            {pipeline.unassigned_stage > 0 && (
              <div className="flex flex-col items-center min-w-[80px]">
                <div className="text-sm font-bold mb-1">{pipeline.unassigned_stage}</div>
                <div className="w-full bg-gray-600 rounded-t" style={{ height: `${Math.max(20, Math.min(120, pipeline.unassigned_stage * 10))}px` }} />
                <div className="text-[10px] text-[var(--color-text-muted)] mt-1 text-center">Unassigned</div>
              </div>
            )}
            {pipeline.stages.map((stage: any) => (
              <div key={stage.id} className="flex flex-col items-center min-w-[80px]">
                <div className="text-sm font-bold mb-1">{stage.entry_count}</div>
                <div
                  className="w-full bg-sky-500 rounded-t"
                  style={{ height: `${Math.max(20, Math.min(120, stage.entry_count * 10))}px` }}
                />
                <div className="text-[10px] text-[var(--color-text-muted)] mt-1 text-center truncate max-w-[80px]">{stage.name}</div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── Throughput Chart (simple bar representation) ── */}
      {throughput && (
        <Card>
          <h3 className="text-sm font-medium mb-3 flex items-center gap-1.5">
            <TrendingUp size={14} className="text-green-400" /> Throughput (Last 30 Days)
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-xs text-[var(--color-text-muted)] mb-2">Submitted ({throughput.submitted_by_day.reduce((s, d) => s + d.count, 0)} total)</div>
              <div className="flex items-end gap-[2px] h-16">
                {throughput.submitted_by_day.slice(-14).map((d, i) => {
                  const maxCount = Math.max(1, ...throughput.submitted_by_day.map(x => x.count));
                  return (
                    <div key={i} className="flex-1 bg-sky-500 rounded-t min-w-[4px]"
                      style={{ height: `${(d.count / maxCount) * 100}%` }}
                      title={`${d.date}: ${d.count}`} />
                  );
                })}
              </div>
            </div>
            <div>
              <div className="text-xs text-[var(--color-text-muted)] mb-2">Decided ({throughput.decided_by_day.reduce((s, d) => s + d.count, 0)} total)</div>
              <div className="flex items-end gap-[2px] h-16">
                {throughput.decided_by_day.slice(-14).map((d, i) => {
                  const maxCount = Math.max(1, ...throughput.decided_by_day.map(x => x.count));
                  return (
                    <div key={i} className="flex-1 bg-emerald-500 rounded-t min-w-[4px]"
                      style={{ height: `${(d.count / maxCount) * 100}%` }}
                      title={`${d.date}: ${d.count}`} />
                  );
                })}
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* ── Team Performance ── */}
      {team.length > 0 && (
        <Card>
          <h3 className="text-sm font-medium mb-3 flex items-center gap-1.5">
            <Users size={14} className="text-purple-400" /> Team Performance (30d)
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                  <th className="text-left py-2 font-medium">Name</th>
                  <th className="text-right py-2 font-medium">Decisions</th>
                  <th className="text-right py-2 font-medium">Avg Turnaround</th>
                  <th className="text-right py-2 font-medium">Throughput/Day</th>
                </tr>
              </thead>
              <tbody>
                {team.sort((a, b) => b.decisions_30d - a.decisions_30d).map(m => (
                  <tr key={m.user_id} className="border-b border-[var(--color-border)]/50">
                    <td className="py-2 font-medium">{m.name}</td>
                    <td className="py-2 text-right">{m.decisions_30d}</td>
                    <td className="py-2 text-right">
                      {m.avg_turnaround_hours ? (
                        <span className={m.avg_turnaround_hours < 24 ? 'text-green-400' : m.avg_turnaround_hours < 72 ? 'text-amber-400' : 'text-red-400'}>
                          {m.avg_turnaround_hours}h
                        </span>
                      ) : '-'}
                    </td>
                    <td className="py-2 text-right text-[var(--color-text-muted)]">{(m.decisions_30d / 30).toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* ── AI Insights ── */}
      {insights.length > 0 && (
        <Card>
          <h3 className="text-sm font-medium mb-3 flex items-center gap-1.5">
            <Brain size={14} className="text-purple-400" /> AI Insights
          </h3>
          <div className="space-y-3">
            {insights.map((ins, i) => (
              <div key={i} className={`flex gap-3 p-3 rounded-lg border ${
                ins.severity === 'warning' ? 'border-amber-500/30 bg-amber-500/5' :
                'border-[var(--color-border)] bg-[var(--color-surface)]'
              }`}>
                {insightIcon(ins.severity)}
                <div className="flex-1">
                  <div className="text-sm font-medium">{ins.title}</div>
                  <p className="text-xs text-[var(--color-text-muted)] mt-0.5">{ins.description}</p>
                </div>
                {ins.metric != null && (
                  <div className="text-right shrink-0">
                    <div className="text-lg font-bold">{ins.metric}</div>
                    {ins.unit && <div className="text-[10px] text-[var(--color-text-muted)]">{ins.unit}</div>}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
