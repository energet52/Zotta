import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts';
import {
  TrendingUp, TrendingDown, Shield,
  PauseCircle, Eye, Activity, ChevronRight,
  RefreshCw, Bell, PieChart as PieIcon,
} from 'lucide-react';
import Card from '../../../../components/ui/Card';
import { sectorApi } from '../../../../api/endpoints';

const COLORS = [
  '#0ea5e9', '#8b5cf6', '#f59e0b', '#10b981', '#ef4444',
  '#6366f1', '#ec4899', '#14b8a6', '#f97316', '#84cc16',
  '#a855f7', '#06b6d4', '#e11d48', '#22d3ee', '#facc15',
  '#4ade80', '#fb923c', '#818cf8', '#f472b6', '#2dd4bf',
  '#a3e635', '#c084fc', '#38bdf8',
];

const RISK_COLORS: Record<string, string> = {
  green: '#22C55E',
  amber: '#EAB308',
  red: '#EF4444',
};

const SEVERITY_COLORS: Record<string, string> = {
  informational: '#3B82F6',
  warning: '#EAB308',
  critical: '#EF4444',
};

interface SectorData {
  sector: string;
  loan_count: number;
  total_outstanding: number;
  avg_loan_size: number;
  exposure_pct: number;
  concentration_status: string;
  risk_rating: string;
  on_watchlist: boolean;
  origination_paused: boolean;
  exposure_cap_pct: number | null;
}

interface DashboardData {
  total_outstanding: number;
  total_loan_count: number;
  sector_count: number;
  sectors: SectorData[];
  top_5: SectorData[];
  bottom_5: SectorData[];
  recent_alerts: Array<{
    id: number;
    sector: string;
    severity: string;
    title: string;
    status: string;
    created_at: string;
  }>;
}

export default function SectorDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [heatmap, setHeatmap] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [chartType, setChartType] = useState<'pie' | 'bar'>('pie');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [dashRes, heatRes] = await Promise.all([
        sectorApi.getDashboard(),
        sectorApi.getHeatmap(),
      ]);
      setData(dashRes.data);
      setHeatmap(heatRes.data);
    } catch (err) {
      console.error('Failed to load sector data', err);
    } finally {
      setLoading(false);
    }
  };

  const fmt = (n: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'TTD', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="animate-spin text-[var(--color-primary)]" size={32} />
      </div>
    );
  }

  if (!data) return <div className="text-center py-20 text-[var(--color-text-muted)]">No data available</div>;

  const watchlistCount = data.sectors.filter(s => s.on_watchlist).length;
  const pausedCount = data.sectors.filter(s => s.origination_paused).length;
  const redCount = data.sectors.filter(s => s.concentration_status === 'red').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">Sector Analysis</h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">Portfolio concentration & risk management</p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/backoffice/sector-analysis/policies"
            className="px-4 py-2 text-sm rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors"
          >
            <Shield size={16} className="inline mr-2" />Policies
          </Link>
          <button
            onClick={loadData}
            className="px-4 py-2 text-sm rounded-lg bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary)]/90 transition-colors"
          >
            <RefreshCw size={16} className="inline mr-2" />Refresh
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <Card className="p-4">
          <div className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Total Exposure</div>
          <div className="text-xl font-bold text-[var(--color-text)] mt-1">{fmt(data.total_outstanding)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Active Loans</div>
          <div className="text-xl font-bold text-[var(--color-text)] mt-1">{data.total_loan_count.toLocaleString()}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Sectors</div>
          <div className="text-xl font-bold text-[var(--color-text)] mt-1">{data.sector_count}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Breached Caps</div>
          <div className="text-xl font-bold mt-1" style={{ color: redCount > 0 ? '#EF4444' : '#22C55E' }}>{redCount}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Watchlist</div>
          <div className="text-xl font-bold mt-1" style={{ color: watchlistCount > 0 ? '#EAB308' : '#22C55E' }}>{watchlistCount}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Paused</div>
          <div className="text-xl font-bold mt-1" style={{ color: pausedCount > 0 ? '#EF4444' : '#22C55E' }}>{pausedCount}</div>
        </Card>
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sector Distribution Chart */}
        <Card className="lg:col-span-2 p-4 sm:p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-[var(--color-text)]">
              <PieIcon size={18} className="inline mr-2 text-[var(--color-primary)]" />
              Portfolio Concentration
            </h2>
            <div className="flex gap-1 bg-[var(--color-bg)] rounded-lg p-1">
              <button
                onClick={() => setChartType('pie')}
                className={`px-3 py-1 text-xs rounded-md transition-colors ${chartType === 'pie' ? 'bg-[var(--color-primary)] text-white' : 'text-[var(--color-text-muted)]'}`}
              >
                Donut
              </button>
              <button
                onClick={() => setChartType('bar')}
                className={`px-3 py-1 text-xs rounded-md transition-colors ${chartType === 'bar' ? 'bg-[var(--color-primary)] text-white' : 'text-[var(--color-text-muted)]'}`}
              >
                Bar
              </button>
            </div>
          </div>

          {chartType === 'pie' ? (
            <ResponsiveContainer width="100%" height={360}>
              <PieChart>
                <Pie
                  data={data.sectors}
                  dataKey="total_outstanding"
                  nameKey="sector"
                  cx="50%"
                  cy="50%"
                  innerRadius={80}
                  outerRadius={150}
                  paddingAngle={2}
                  label={(props: { payload?: { sector?: string; exposure_pct?: number } }) => {
                    const sector = props.payload?.sector ?? '';
                    const exposure_pct = props.payload?.exposure_pct ?? 0;
                    return `${sector.length > 15 ? sector.slice(0, 15) + '...' : sector} (${exposure_pct}%)`;
                  }}
                  labelLine={true}
                >
                  {data.sectors.map((_entry, idx) => (
                    <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: number = 0) => fmt(value)}
                  contentStyle={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '8px' }}
                  labelStyle={{ color: 'var(--color-text)' }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <ResponsiveContainer width="100%" height={360}>
              <BarChart data={data.sectors.slice(0, 10)} layout="vertical" margin={{ left: 120 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis type="number" tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} stroke="var(--color-text-muted)" />
                <YAxis type="category" dataKey="sector" width={120} tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} />
                <Tooltip formatter={(value: number = 0) => fmt(value)} contentStyle={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '8px' }} />
                <Bar dataKey="total_outstanding" name="Outstanding" radius={[0, 4, 4, 0]}>
                  {data.sectors.slice(0, 10).map((_entry, idx) => (
                    <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        {/* Recent Alerts */}
        <Card className="p-4 sm:p-6">
          <h2 className="font-semibold text-[var(--color-text)] mb-4">
            <Bell size={18} className="inline mr-2 text-[var(--color-primary)]" />
            Recent Alerts
          </h2>
          <div className="space-y-3 max-h-[340px] overflow-y-auto">
            {data.recent_alerts.length === 0 ? (
              <p className="text-sm text-[var(--color-text-muted)] text-center py-8">No active alerts</p>
            ) : (
              data.recent_alerts.map(alert => (
                <div key={alert.id} className="flex items-start gap-3 p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
                  <div
                    className="w-2 h-2 rounded-full mt-2 flex-shrink-0"
                    style={{ backgroundColor: SEVERITY_COLORS[alert.severity] || '#6B7280' }}
                  />
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-[var(--color-text)] truncate">{alert.title}</div>
                    <div className="text-xs text-[var(--color-text-muted)]">{alert.sector}</div>
                    <div className="text-xs text-[var(--color-text-muted)] mt-1">
                      {alert.created_at ? new Date(alert.created_at).toLocaleDateString() : ''}
                    </div>
                  </div>
                  <span
                    className="text-xs px-2 py-0.5 rounded-full flex-shrink-0 capitalize"
                    style={{
                      backgroundColor: `${SEVERITY_COLORS[alert.severity] || '#6B7280'}20`,
                      color: SEVERITY_COLORS[alert.severity] || '#6B7280',
                    }}
                  >
                    {alert.severity}
                  </span>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>

      {/* Sector Heatmap Table */}
      <Card className="p-4 sm:p-6">
        <h2 className="font-semibold text-[var(--color-text)] mb-4">
          <Activity size={18} className="inline mr-2 text-[var(--color-primary)]" />
          Sector Risk Heatmap
        </h2>
        <div className="overflow-x-auto max-w-full">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-[var(--color-text-muted)] uppercase tracking-wider border-b border-[var(--color-border)]">
                <th className="pb-3 pr-4">Sector</th>
                <th className="pb-3 pr-4 text-right">Exposure %</th>
                <th className="pb-3 pr-4 text-right">Loans</th>
                <th className="pb-3 pr-4 text-right">Delinq. Rate</th>
                <th className="pb-3 pr-4 text-right">NPL Ratio</th>
                <th className="pb-3 pr-4 text-center">Risk</th>
                <th className="pb-3 pr-4 text-center">Concentration</th>
                <th className="pb-3 pr-4 text-center">Status</th>
                <th className="pb-3"></th>
              </tr>
            </thead>
            <tbody>
              {heatmap.map((row, idx) => (
                <tr key={idx} className="border-b border-[var(--color-border)]/50 hover:bg-[var(--color-surface-hover)] transition-colors">
                  <td className="py-3 pr-4 font-medium text-[var(--color-text)]">
                    {row.sector}
                    {row.on_watchlist && (
                      <Eye size={14} className="inline ml-2 text-yellow-500" />
                    )}
                    {row.origination_paused && (
                      <PauseCircle size={14} className="inline ml-2 text-red-500" />
                    )}
                  </td>
                  <td className="py-3 pr-4 text-right tabular-nums">{row.exposure_pct}%</td>
                  <td className="py-3 pr-4 text-right tabular-nums">{row.loan_count}</td>
                  <td className="py-3 pr-4 text-right">
                    <span style={{ color: row.delinquency_rate > 10 ? '#EF4444' : row.delinquency_rate > 5 ? '#EAB308' : '#22C55E' }}>
                      {row.delinquency_rate}%
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-right">
                    <span style={{ color: row.npl_ratio > 5 ? '#EF4444' : row.npl_ratio > 2 ? '#EAB308' : '#22C55E' }}>
                      {row.npl_ratio}%
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-center">
                    <span className={`px-2 py-0.5 rounded-full text-xs capitalize ${
                      row.risk_rating === 'critical' ? 'bg-red-500/20 text-red-400' :
                      row.risk_rating === 'very_high' ? 'bg-orange-500/20 text-orange-400' :
                      row.risk_rating === 'high' ? 'bg-yellow-500/20 text-yellow-400' :
                      row.risk_rating === 'medium' ? 'bg-blue-500/20 text-blue-400' :
                      'bg-green-500/20 text-green-400'
                    }`}>
                      {row.risk_rating?.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-center">
                    <div
                      className="w-3 h-3 rounded-full mx-auto"
                      style={{ backgroundColor: RISK_COLORS[row.concentration_status] || '#6B7280' }}
                      title={`Concentration: ${row.concentration_status}`}
                    />
                  </td>
                  <td className="py-3 pr-4 text-center">
                    <div className="flex items-center gap-1">
                      {row.origination_paused && (
                        <span className="px-2 py-0.5 rounded-full text-xs bg-red-500/20 text-red-400">Paused</span>
                      )}
                      {row.on_watchlist && (
                        <span className="px-2 py-0.5 rounded-full text-xs bg-yellow-500/20 text-yellow-400">Watch</span>
                      )}
                    </div>
                  </td>
                  <td className="py-3">
                    <Link
                      to={`/backoffice/sector-analysis/${encodeURIComponent(row.sector)}`}
                      className="text-[var(--color-primary)] hover:underline"
                    >
                      <ChevronRight size={16} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Top / Bottom Sectors */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="p-4 sm:p-6">
          <h2 className="font-semibold text-[var(--color-text)] mb-3">
            <TrendingUp size={18} className="inline mr-2 text-green-400" />
            Top 5 Sectors by Exposure
          </h2>
          <div className="space-y-2">
            {data.top_5.map((s, idx) => (
              <Link
                key={idx}
                to={`/backoffice/sector-analysis/${encodeURIComponent(s.sector)}`}
                className="flex items-center justify-between p-3 rounded-lg bg-[var(--color-bg)] hover:bg-[var(--color-surface-hover)] transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold" style={{ backgroundColor: `${COLORS[idx]}30`, color: COLORS[idx] }}>
                    {idx + 1}
                  </div>
                  <span className="text-sm text-[var(--color-text)]">{s.sector}</span>
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium text-[var(--color-text)]">{fmt(s.total_outstanding)}</div>
                  <div className="text-xs text-[var(--color-text-muted)]">{s.exposure_pct}% | {s.loan_count} loans</div>
                </div>
              </Link>
            ))}
          </div>
        </Card>

        <Card className="p-4 sm:p-6">
          <h2 className="font-semibold text-[var(--color-text)] mb-3">
            <TrendingDown size={18} className="inline mr-2 text-red-400" />
            Bottom 5 Sectors by Exposure
          </h2>
          <div className="space-y-2">
            {data.bottom_5.map((s, idx) => (
              <Link
                key={idx}
                to={`/backoffice/sector-analysis/${encodeURIComponent(s.sector)}`}
                className="flex items-center justify-between p-3 rounded-lg bg-[var(--color-bg)] hover:bg-[var(--color-surface-hover)] transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold bg-gray-500/20 text-gray-400">
                    {data.sectors.length - data.bottom_5.length + idx + 1}
                  </div>
                  <span className="text-sm text-[var(--color-text)]">{s.sector}</span>
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium text-[var(--color-text)]">{fmt(s.total_outstanding)}</div>
                  <div className="text-xs text-[var(--color-text-muted)]">{s.exposure_pct}% | {s.loan_count} loans</div>
                </div>
              </Link>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
