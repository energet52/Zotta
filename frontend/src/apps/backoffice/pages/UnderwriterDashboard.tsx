import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  FileText, CheckCircle, XCircle, Clock, TrendingUp, DollarSign,
  AlertTriangle, ArrowRight, Banknote, Activity, BarChart3
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import { reportsApi } from '../../../api/endpoints';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line,
  Area, AreaChart
} from 'recharts';

interface DashboardData {
  total_applications: number;
  pending_review: number;
  approved: number;
  declined: number;
  total_disbursed: number;
  approval_rate: number;
  avg_processing_days: number;
  avg_loan_amount: number;
  applications_by_status: Record<string, number>;
  risk_distribution: Record<string, number>;
  monthly_volume: { year: number; month: number; count: number; volume: number }[];
  projected_interest_income: number;
  total_principal_disbursed: number;
  projected_profit: number;
  daily_volume: { date: string; count: number; volume: number }[];
}

const RISK_COLORS: Record<string, string> = {
  A: '#34d399', B: '#22d3ee', C: '#fbbf24', D: '#f97316', E: '#f87171',
};
const RISK_LABELS: Record<string, string> = {
  A: 'Low Risk', B: 'Moderate', C: 'Medium', D: 'Elevated', E: 'High Risk',
};

export default function UnderwriterDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    reportsApi.getDashboard()
      .then((res) => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-12 text-[var(--color-text-muted)]">Loading dashboard...</div>;
  if (!data) return <div className="text-center py-12 text-[var(--color-danger)]">Failed to load dashboard</div>;

  const riskData = Object.entries(data.risk_distribution).map(([band, count]) => ({
    name: `Band ${band}`, label: RISK_LABELS[band] || band, value: count, fill: RISK_COLORS[band] || '#64748b',
  }));

  const monthlyData = data.monthly_volume.map((m) => ({
    name: `${m.year}-${String(m.month).padStart(2, '0')}`,
    count: m.count,
    volume: m.volume / 1000,
  }));

  const dailyData = (data.daily_volume || []).map(d => ({
    date: d.date.slice(5),  // MM-DD
    count: d.count,
    volume: d.volume / 1000,
  }));

  const disbursedCount = data.applications_by_status?.disbursed || 0;
  const fmt = (val: number) => `TTD ${val.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">Dashboard</h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">Lending Operations Overview</p>
        </div>
        <Link
          to="/backoffice/applications"
          className="inline-flex items-center text-sm text-[var(--color-primary)] hover:text-[var(--color-primary-light)] transition-colors"
        >
          View Queue <ArrowRight size={16} className="ml-1" />
        </Link>
      </div>

      {/* KPI Cards - Clickable */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <div onClick={() => navigate('/backoffice/loans')} className="cursor-pointer group">
          <Card padding="sm" className="transition-all group-hover:border-[var(--color-primary)]/50">
            <p className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider mb-2">Total Applications</p>
            <p className="text-3xl font-bold text-[var(--color-text)]">{data.total_applications}</p>
            <p className="text-xs text-[var(--color-text-muted)] mt-1">All time</p>
          </Card>
        </div>

        <div onClick={() => navigate('/backoffice/applications')} className="cursor-pointer group">
          <Card padding="sm" className="transition-all group-hover:border-[var(--color-warning)]/50">
            <p className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider mb-2">Pending Review</p>
            <p className="text-3xl font-bold text-[var(--color-warning)]">{data.pending_review}</p>
            <p className="text-xs text-[var(--color-text-muted)] mt-1">
              {data.pending_review > 0 ? (
                <span className="text-[var(--color-warning)] flex items-center"><AlertTriangle size={11} className="mr-1" />Needs attention</span>
              ) : 'All clear'}
            </p>
          </Card>
        </div>

        <div onClick={() => navigate('/backoffice/loans?status=approved')} className="cursor-pointer group">
          <Card padding="sm" className="transition-all group-hover:border-[var(--color-success)]/50">
            <p className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider mb-2">Approval Rate</p>
            <p className="text-3xl font-bold text-[var(--color-success)]">{data.approval_rate}%</p>
            <p className="text-xs text-[var(--color-text-muted)] mt-1">{data.approved} approved / {data.declined} declined</p>
          </Card>
        </div>

        <div onClick={() => navigate('/backoffice/loans')} className="cursor-pointer group">
          <Card padding="sm" className="transition-all group-hover:border-[var(--color-primary)]/50">
            <p className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider mb-2">Avg Loan Amount</p>
            <p className="text-3xl font-bold text-[var(--color-primary)]">
              <span className="text-lg">TTD</span> {(data.avg_loan_amount / 1000).toFixed(0)}k
            </p>
            <p className="text-xs text-[var(--color-text-muted)] mt-1">Per application</p>
          </Card>
        </div>

        <div onClick={() => navigate('/backoffice/applications')} className="cursor-pointer group">
          <Card padding="sm" className="transition-all group-hover:border-[var(--color-cyan,#22d3ee)]/50">
            <p className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider mb-2">Avg Processing</p>
            <p className="text-3xl font-bold text-[var(--color-cyan,#22d3ee)]">{data.avg_processing_days}</p>
            <p className="text-xs text-[var(--color-text-muted)] mt-1">Days to decision</p>
          </Card>
        </div>
      </div>

      {/* Disbursed + P&L Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <div onClick={() => navigate('/backoffice/loans?status=disbursed')} className="cursor-pointer">
          <Card padding="sm" className="border-[var(--color-success)]/30 hover:border-[var(--color-success)]/60 transition-all">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="w-10 h-10 rounded-lg bg-[var(--color-success)]/15 flex items-center justify-center">
                  <Banknote size={20} className="text-[var(--color-success)]" />
                </div>
                <div>
                  <p className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">Total Disbursed</p>
                  <p className="text-2xl font-bold text-[var(--color-success)]">
                    TTD {data.total_disbursed.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium text-[var(--color-text)]">{disbursedCount} loans</p>
                <p className="text-xs text-[var(--color-text-muted)]">disbursed to date</p>
              </div>
            </div>
          </Card>
        </div>

        {/* P&L Card */}
        <Card padding="sm" className="border-[var(--color-cyan,#22d3ee)]/30">
          <div className="flex items-center space-x-4 mb-3">
            <div className="w-10 h-10 rounded-lg bg-[var(--color-cyan,#22d3ee)]/15 flex items-center justify-center">
              <TrendingUp size={20} className="text-[var(--color-cyan,#22d3ee)]" />
            </div>
            <div>
              <p className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">Profit & Loss Projection</p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-[var(--color-text-muted)]">Interest Income</p>
              <p className="text-lg font-bold text-[var(--color-success)]">{fmt(data.projected_interest_income)}</p>
            </div>
            <div>
              <p className="text-xs text-[var(--color-text-muted)]">Principal at Risk</p>
              <p className="text-lg font-bold text-[var(--color-warning)]">{fmt(data.total_principal_disbursed)}</p>
            </div>
            <div>
              <p className="text-xs text-[var(--color-text-muted)]">Est. Profit</p>
              <p className={`text-lg font-bold ${data.projected_profit >= 0 ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'}`}>
                {fmt(data.projected_profit)}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Monthly Volume */}
        <Card>
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-[var(--color-text)]">Monthly Volume</h3>
            <span className="text-xs text-[var(--color-text-muted)]">Last 12 months</span>
          </div>
          {monthlyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={monthlyData}>
                <defs>
                  <linearGradient id="colorVolume" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#38bdf8" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} stroke="var(--color-border)" />
                <YAxis tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} stroke="var(--color-border)" />
                <Tooltip contentStyle={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '8px', color: 'var(--color-text)' }} />
                <Area type="monotone" dataKey="count" stroke="#38bdf8" fill="url(#colorVolume)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-center text-[var(--color-text-muted)] py-12">No data available</p>
          )}
        </Card>

        {/* Risk Distribution */}
        <Card>
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-[var(--color-text)]">Risk Distribution</h3>
            <span className="text-xs text-[var(--color-text-muted)]">All decisions</span>
          </div>
          {riskData.length > 0 ? (
            <div className="flex items-center">
              <ResponsiveContainer width="50%" height={200}>
                <PieChart>
                  <Pie data={riskData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" paddingAngle={2}>
                    {riskData.map((entry, i) => (<Cell key={i} fill={entry.fill} />))}
                  </Pie>
                  <Tooltip contentStyle={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '8px', color: 'var(--color-text)' }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex-1 space-y-2">
                {riskData.map((entry) => (
                  <div key={entry.name} className="flex items-center justify-between text-sm">
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: entry.fill }} />
                      <span className="text-[var(--color-text-muted)]">{entry.name}</span>
                    </div>
                    <span className="font-medium text-[var(--color-text)]">{entry.value}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-center text-[var(--color-text-muted)] py-12">No data available</p>
          )}
        </Card>
      </div>

      {/* Daily Volume Chart */}
      {dailyData.length > 0 && (
        <Card className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-[var(--color-text)]">Daily Application Volume</h3>
            <span className="text-xs text-[var(--color-text-muted)]">Last 30 days</span>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={dailyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }} stroke="var(--color-border)" />
              <YAxis tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} stroke="var(--color-border)" />
              <Tooltip contentStyle={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '8px', color: 'var(--color-text)' }} />
              <Bar dataKey="count" fill="#a78bfa" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Status Breakdown */}
      <Card>
        <h3 className="font-semibold text-[var(--color-text)] mb-4">Applications by Status</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {Object.entries(data.applications_by_status).map(([status, count]) => {
            const statusColors: Record<string, string> = {
              draft: '#64748b', submitted: '#38bdf8', under_review: '#38bdf8',
              credit_check: '#a78bfa', decision_pending: '#fbbf24', approved: '#34d399',
              declined: '#f87171', disbursed: '#22d3ee', cancelled: '#64748b',
              offer_sent: '#34d399', accepted: '#34d399', rejected_by_applicant: '#f87171',
              counter_proposed: '#a78bfa', awaiting_documents: '#fbbf24',
            };
            const color = statusColors[status] || '#64748b';
            return (
              <div
                key={status}
                className="text-center p-3 rounded-lg bg-[var(--color-bg)] cursor-pointer hover:ring-1 hover:ring-[var(--color-primary)]/30 transition-all"
                onClick={() => navigate(`/backoffice/loans?status=${status}`)}
              >
                <p className="text-2xl font-bold" style={{ color }}>{count}</p>
                <p className="text-xs text-[var(--color-text-muted)] capitalize mt-1">{status.replace(/_/g, ' ')}</p>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
