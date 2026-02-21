import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  CheckCircle, TrendingUp, DollarSign,
  AlertTriangle, ArrowRight
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import { reportsApi } from '../../../api/endpoints';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Area, AreaChart
} from 'recharts';

interface ArrearsBucket {
  label: string;
  loan_count: number;
  total_outstanding: number;
  total_overdue: number;
}

interface ArrearsSummary {
  total_delinquent_loans: number;
  total_overdue_amount: number;
  total_outstanding_at_risk: number;
  buckets: ArrearsBucket[];
}

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
  arrears_summary: ArrearsSummary | null;
  interest_collected: number;
  expected_default_loss: number;
  net_pnl: number;
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

      {/* Live P&L Panel */}
      <div className="mb-6">
        <div className="relative rounded-xl border-2 border-transparent bg-gradient-to-r from-emerald-500/10 via-sky-500/10 to-rose-500/10 p-[2px]">
          <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-emerald-500/40 via-sky-500/30 to-rose-500/40 blur-sm -z-10" />
          <div className="rounded-[10px] bg-[var(--color-surface)] p-5">
            <div className="flex items-center space-x-3 mb-4">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500/20 to-sky-500/20 flex items-center justify-center">
                <DollarSign size={20} className="text-emerald-500" />
              </div>
              <div>
                <h3 className="font-bold text-[var(--color-text)]">Live Portfolio P&L</h3>
                <p className="text-[11px] text-[var(--color-text-muted)]">Real-time profit & loss based on actual collections</p>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              <div className="text-center p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                <p className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider mb-1">Interest Earned</p>
                <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{fmt(data.interest_collected)}</p>
                <p className="text-[10px] text-[var(--color-text-muted)] mt-1">Collected from paid instalments</p>
              </div>
              <div className="text-center p-4 rounded-lg bg-rose-500/5 border border-rose-500/20">
                <p className="text-xs font-semibold text-rose-600 dark:text-rose-400 uppercase tracking-wider mb-1">Expected Losses (60+ DPD)</p>
                <p className="text-2xl font-bold text-rose-600 dark:text-rose-400">{fmt(data.expected_default_loss)}</p>
                <p className="text-[10px] text-[var(--color-text-muted)] mt-1">Outstanding on likely defaults</p>
              </div>
              <div className={`text-center p-4 rounded-lg border ${
                data.net_pnl >= 0
                  ? 'bg-emerald-500/5 border-emerald-500/20'
                  : 'bg-rose-500/5 border-rose-500/20'
              }`}>
                <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-1">Net P&L</p>
                <p className={`text-2xl font-bold ${data.net_pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                  {data.net_pnl >= 0 ? '+' : ''}{fmt(data.net_pnl)}
                </p>
                <p className="text-[10px] text-[var(--color-text-muted)] mt-1">
                  {data.net_pnl >= 0 ? 'Portfolio is profitable' : 'Portfolio at risk'}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* KPI Cards - Clickable */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <div onClick={() => navigate('/backoffice/loans')} className="cursor-pointer group">
          <Card padding="sm" className="transition-all group-hover:border-[var(--color-primary)]/50">
            <p className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider mb-2">Total Applications</p>
            <p className="text-3xl font-bold text-[var(--color-text)]">{data.total_applications}</p>
            <p className="text-xs text-[var(--color-text-muted)] mt-1">All time</p>
          </Card>
        </div>

        <div onClick={() => navigate('/backoffice/applications?status_filter=decision_pending')} className="cursor-pointer group">
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

      {/* Profit & Loss Projection (includes Total Disbursed) */}
      <div
        onClick={() => navigate('/backoffice/loans?status=disbursed')}
        className="cursor-pointer mb-6"
      >
        <Card padding="sm" className="border-[var(--color-cyan,#22d3ee)]/30 hover:border-[var(--color-cyan,#22d3ee)]/60 transition-all">
          <div className="flex items-center space-x-4 mb-3">
            <div className="w-10 h-10 rounded-lg bg-[var(--color-cyan,#22d3ee)]/15 flex items-center justify-center">
              <TrendingUp size={20} className="text-[var(--color-cyan,#22d3ee)]" />
            </div>
            <div>
              <p className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">Profit & Loss Projection</p>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 sm:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-[var(--color-text-muted)]">Total Disbursed</p>
              <p className="text-lg font-bold text-[var(--color-success)]">
                {fmt(data.total_disbursed)}
              </p>
              <p className="text-xs text-[var(--color-text-muted)]">{disbursedCount} loans</p>
            </div>
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

      {/* Arrears / Delinquency Summary */}
      {data.arrears_summary && (
        <div className="mb-6">
          <Card padding="sm" className={data.arrears_summary.total_delinquent_loans > 0 ? 'border-red-400/40' : ''}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                  data.arrears_summary.total_delinquent_loans > 0
                    ? 'bg-red-500/15'
                    : 'bg-green-500/15'
                }`}>
                  <AlertTriangle size={20} className={
                    data.arrears_summary.total_delinquent_loans > 0 ? 'text-red-500' : 'text-green-500'
                  } />
                </div>
                <div>
                  <h3 className="font-semibold text-[var(--color-text)]">Portfolio Arrears</h3>
                  <p className="text-xs text-[var(--color-text-muted)]">Aged delinquency report</p>
                </div>
              </div>
              {data.arrears_summary.total_delinquent_loans > 0 && (
                <div
                  onClick={() => navigate('/backoffice/loans?arrears=1')}
                  className="cursor-pointer flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 transition-colors"
                >
                  <span className="text-sm font-bold text-red-500">{data.arrears_summary.total_delinquent_loans}</span>
                  <span className="text-xs text-red-400">delinquent loan{data.arrears_summary.total_delinquent_loans !== 1 ? 's' : ''}</span>
                  <ArrowRight size={14} className="text-red-400" />
                </div>
              )}
            </div>

            {data.arrears_summary.total_delinquent_loans > 0 ? (
              <>
                {/* Summary stats row */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
                  <div
                    onClick={() => navigate('/backoffice/loans?arrears=1')}
                    className="cursor-pointer rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 p-3 text-center hover:border-red-400 transition-colors"
                  >
                    <p className="text-xs text-red-500 uppercase font-semibold tracking-wider mb-1">Total Overdue</p>
                    <p className="text-xl font-bold text-red-600 dark:text-red-400">{fmt(data.arrears_summary.total_overdue_amount)}</p>
                  </div>
                  <div className="rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 p-3 text-center">
                    <p className="text-xs text-amber-600 dark:text-amber-400 uppercase font-semibold tracking-wider mb-1">Outstanding at Risk</p>
                    <p className="text-xl font-bold text-amber-600 dark:text-amber-400">{fmt(data.arrears_summary.total_outstanding_at_risk)}</p>
                  </div>
                  <div
                    onClick={() => navigate('/backoffice/loans?arrears=1')}
                    className="cursor-pointer rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] p-3 text-center hover:border-red-400 transition-colors"
                  >
                    <p className="text-xs text-[var(--color-text-muted)] uppercase font-semibold tracking-wider mb-1">Delinquent Loans</p>
                    <p className="text-xl font-bold text-red-500">{data.arrears_summary.total_delinquent_loans}</p>
                    <p className="text-[10px] text-[var(--color-text-muted)]">Click to view</p>
                  </div>
                </div>

                {/* Aged buckets */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  {data.arrears_summary.buckets.map((bucket) => {
                    const colors = {
                      '1–30 days': { bg: 'bg-yellow-50 dark:bg-yellow-950/20', border: 'border-yellow-300 dark:border-yellow-800', text: 'text-yellow-600 dark:text-yellow-400', bar: 'bg-yellow-400' },
                      '31–60 days': { bg: 'bg-orange-50 dark:bg-orange-950/20', border: 'border-orange-300 dark:border-orange-800', text: 'text-orange-600 dark:text-orange-400', bar: 'bg-orange-400' },
                      '61–90 days': { bg: 'bg-red-50 dark:bg-red-950/20', border: 'border-red-300 dark:border-red-800', text: 'text-red-500', bar: 'bg-red-400' },
                      '90+ days': { bg: 'bg-red-100 dark:bg-red-950/40', border: 'border-red-400 dark:border-red-700', text: 'text-red-600 dark:text-red-400', bar: 'bg-red-600' },
                    };
                    const c = colors[bucket.label as keyof typeof colors] || colors['90+ days'];
                    const pct = data.arrears_summary!.total_overdue_amount > 0
                      ? Math.round((bucket.total_overdue / data.arrears_summary!.total_overdue_amount) * 100)
                      : 0;

                    return (
                      <div key={bucket.label} className={`rounded-lg ${c.bg} border ${c.border} p-3`}>
                        <p className={`text-[10px] uppercase font-bold tracking-wider mb-2 ${c.text}`}>{bucket.label}</p>
                        <p className={`text-lg font-bold ${c.text}`}>{bucket.loan_count}</p>
                        <p className="text-[10px] text-[var(--color-text-muted)]">
                          loan{bucket.loan_count !== 1 ? 's' : ''}
                        </p>
                        {bucket.total_overdue > 0 && (
                          <div className="mt-2 pt-2 border-t border-[var(--color-border)]/50">
                            <p className="text-xs text-[var(--color-text-muted)]">Overdue</p>
                            <p className={`text-sm font-semibold ${c.text}`}>{fmt(bucket.total_overdue)}</p>
                            {/* Mini progress bar showing proportion */}
                            <div className="mt-1 h-1 rounded-full bg-[var(--color-border)] overflow-hidden">
                              <div className={`h-full rounded-full ${c.bar}`} style={{ width: `${pct}%` }} />
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </>
            ) : (
              <div className="text-center py-4">
                <CheckCircle size={24} className="mx-auto text-green-500 mb-2" />
                <p className="text-sm text-green-600 dark:text-green-400 font-medium">No loans in arrears</p>
                <p className="text-xs text-[var(--color-text-muted)]">All payments are current</p>
              </div>
            )}
          </Card>
        </div>
      )}

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
        <div className="grid grid-cols-1 sm:grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {Object.entries(data.applications_by_status)
            .filter(([status]) =>
              ['draft', 'disbursed', 'declined', 'decision_pending', 'rejected_by_applicant', 'approved', 'cancelled', 'counter_proposed'].includes(status)
            )
            .map(([status, count]) => {
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
                onClick={() => navigate(status === 'disbursed' ? '/backoffice/loans' : `/backoffice/applications?status_filter=${status}`)}
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
