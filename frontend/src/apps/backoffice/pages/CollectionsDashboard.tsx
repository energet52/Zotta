import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  BarChart3, TrendingDown, Users, DollarSign, Clock, CheckCircle,
  ArrowRight, AlertTriangle, RefreshCw,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid, Legend,
} from 'recharts';
import Card from '../../../components/ui/Card';
import Badge from '../../../components/ui/Badge';
import Button from '../../../components/ui/Button';
import { collectionsApi } from '../../../api/endpoints';

interface DashboardData {
  total_delinquent_accounts: number;
  total_overdue_amount: number;
  by_stage: Record<string, { count: number; amount: number }>;
  trend: Array<{ date: string; total_overdue: number; accounts: number; recovered: number }>;
  cure_rate: number;
  ptp_rate: number;
  ptp_kept_rate: number;
  recovered_mtd: number;
}

interface AgentPerf {
  agent_id: number;
  name: string;
  total_cases: number;
  resolved_cases: number;
  resolution_rate: number;
  total_overdue: number;
  ptp_kept: number;
  ptp_total: number;
  ptp_kept_rate: number;
}

const STAGE_LABELS: Record<string, string> = {
  early_1_30: 'Early (1-30)',
  mid_31_60: 'Mid (31-60)',
  late_61_90: 'Late (61-90)',
  severe_90_plus: 'Severe (90+)',
  default: 'Default',
  write_off: 'Write-Off',
};

const STAGE_COLORS: Record<string, string> = {
  early_1_30: '#facc15',
  mid_31_60: '#fb923c',
  late_61_90: '#f87171',
  severe_90_plus: '#ef4444',
  default: '#dc2626',
  write_off: '#991b1b',
};

export default function CollectionsDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [agents, setAgents] = useState<AgentPerf[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => { load(); }, []);

  const load = async () => {
    try {
      const [dashRes, agentRes] = await Promise.all([
        collectionsApi.getDashboard(30),
        collectionsApi.getAgentPerformance(),
      ]);
      setData(dashRes.data);
      setAgents(agentRes.data);
    } catch { /* ignore */ }
    setLoading(false);
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      await collectionsApi.syncCases();
      await load();
    } catch { /* ignore */ }
    setSyncing(false);
  };

  const fmt = (n: number) => `TTD ${n.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
  const pct = (n: number) => `${(n * 100).toFixed(1)}%`;

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-[var(--color-text-muted)]">Loading dashboard...</div>;
  }

  const agingData = data?.by_stage
    ? Object.entries(data.by_stage).map(([stage, v]) => ({
        stage: STAGE_LABELS[stage] || stage,
        count: v.count,
        amount: v.amount,
        fill: STAGE_COLORS[stage] || '#94a3b8',
      }))
    : [];

  const trendData = data?.trend || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-[var(--color-danger)]/15 rounded-lg">
            <BarChart3 className="text-[var(--color-danger)]" size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Collections Dashboard</h1>
            <p className="text-sm text-[var(--color-text-muted)]">Portfolio health and recovery metrics</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={handleSync} disabled={syncing}>
            <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
            <span className="ml-1">{syncing ? 'Syncing...' : 'Sync Cases'}</span>
          </Button>
          <Link to="/backoffice/collections">
            <Button>
              View Queue <ArrowRight size={14} className="ml-1" />
            </Button>
          </Link>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <Card>
          <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1">
            <AlertTriangle size={12} /> Delinquent
          </div>
          <div className="text-2xl font-bold text-[var(--color-danger)]">{data?.total_delinquent_accounts ?? 0}</div>
        </Card>
        <Card>
          <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1">
            <DollarSign size={12} /> Total Overdue
          </div>
          <div className="text-lg font-bold text-[var(--color-danger)]">{fmt(data?.total_overdue_amount ?? 0)}</div>
        </Card>
        <Card>
          <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1">
            <CheckCircle size={12} /> Cure Rate
          </div>
          <div className="text-2xl font-bold text-emerald-400">{pct(data?.cure_rate ?? 0)}</div>
        </Card>
        <Card>
          <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1">
            <TrendingDown size={12} /> PTP Kept
          </div>
          <div className="text-2xl font-bold text-[var(--color-primary)]">{pct(data?.ptp_kept_rate ?? 0)}</div>
        </Card>
        <Card>
          <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1">
            <Clock size={12} /> Avg Collection
          </div>
          <div className="text-2xl font-bold text-[var(--color-text)]">{data ? `${(data as any).avg_days_to_collect || 0}d` : '—'}</div>
        </Card>
        <Card>
          <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1">
            <DollarSign size={12} /> Recovered MTD
          </div>
          <div className="text-lg font-bold text-emerald-400">{fmt(data?.recovered_mtd ?? 0)}</div>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Aging Bucket Chart */}
        <Card>
          <h3 className="font-semibold text-[var(--color-text)] mb-4">DPD Aging Buckets</h3>
          {agingData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={agingData}>
                <XAxis dataKey="stage" tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} />
                <YAxis tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} />
                <Tooltip
                  contentStyle={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8 }}
                  labelStyle={{ color: 'var(--color-text)' }}
                  formatter={(value, name) => [
                    name === 'count' ? (Number(value) ?? 0) : fmt(Number(value) ?? 0),
                    name === 'count' ? 'Accounts' : 'Amount',
                  ]}
                />
                <Bar dataKey="count" name="count" fill="#f87171" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-64 flex items-center justify-center text-[var(--color-text-muted)]">No data</div>
          )}
        </Card>

        {/* Trend Line */}
        <Card>
          <h3 className="font-semibold text-[var(--color-text)] mb-4">Overdue Trend (30 Days)</h3>
          {trendData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                  tickFormatter={(v) => new Date(v).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                />
                <YAxis tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} />
                <Tooltip
                  contentStyle={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8 }}
                  formatter={(value) => [fmt(Number(value) ?? 0)]}
                />
                <Legend />
                <Line type="monotone" dataKey="total_overdue" stroke="#ef4444" name="Overdue" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="recovered" stroke="#22c55e" name="Recovered MTD" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-64 flex items-center justify-center text-[var(--color-text-muted)]">No trend data</div>
          )}
        </Card>
      </div>

      {/* Agent Performance */}
      <Card>
        <h3 className="font-semibold text-[var(--color-text)] mb-4 flex items-center gap-2">
          <Users size={16} /> Agent Performance
        </h3>
        {agents.length > 0 ? (
          <div className="overflow-x-auto max-w-full">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                  <th className="px-3 py-2 text-left">Agent</th>
                  <th className="px-3 py-2 text-right">Cases</th>
                  <th className="px-3 py-2 text-right">Resolved</th>
                  <th className="px-3 py-2 text-right">Rate</th>
                  <th className="px-3 py-2 text-right">Overdue</th>
                  <th className="px-3 py-2 text-right">PTP Kept</th>
                </tr>
              </thead>
              <tbody>
                {agents.map((a) => (
                  <tr key={a.agent_id} className="border-b border-[var(--color-border)]">
                    <td className="px-3 py-2 font-medium">{a.name}</td>
                    <td className="px-3 py-2 text-right">{a.total_cases}</td>
                    <td className="px-3 py-2 text-right">{a.resolved_cases}</td>
                    <td className="px-3 py-2 text-right">
                      <Badge variant={a.resolution_rate > 0.5 ? 'success' : a.resolution_rate > 0.25 ? 'warning' : 'danger'}>
                        {pct(a.resolution_rate)}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 text-right text-[var(--color-danger)]">{fmt(a.total_overdue)}</td>
                    <td className="px-3 py-2 text-right">{a.ptp_kept}/{a.ptp_total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-8 text-center text-[var(--color-text-muted)]">No agent data available</div>
        )}
      </Card>
    </div>
  );
}
