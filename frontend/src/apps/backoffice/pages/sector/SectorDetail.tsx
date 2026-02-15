import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  AreaChart, Area, ResponsiveContainer, XAxis, YAxis, CartesianGrid, Tooltip,
  BarChart, Bar, Cell, Legend,
} from 'recharts';
import {
  ArrowLeft, TrendingUp, TrendingDown, AlertTriangle,
  Shield, PauseCircle, Eye, RefreshCw, Activity,
  ChevronRight, FileText, BarChart3,
} from 'lucide-react';
import Card from '../../../../components/ui/Card';
import { sectorApi } from '../../../../api/endpoints';

interface DPDBucket {
  count: number;
  amount: number;
}

interface SectorDetailData {
  sector: string;
  loan_count: number;
  total_outstanding: number;
  avg_loan_size: number;
  exposure_pct: number;
  portfolio_total: number;
  portfolio_count: number;
  current_count: number;
  delinquent_count: number;
  delinquency_rate: number;
  npl_ratio: number;
  dpd_30: DPDBucket;
  dpd_60: DPDBucket;
  dpd_90: DPDBucket;
  roll_rates: { current_to_30: number; dpd30_to_60: number; dpd60_to_90: number };
  policy: any | null;
  snapshots: Array<{
    date: string;
    loan_count: number;
    total_outstanding: number;
    exposure_pct: number;
    delinquency_rate: number;
    npl_ratio: number;
    dpd_30_count: number;
    dpd_60_count: number;
    dpd_90_count: number;
  }>;
  loans: Array<{
    id: number;
    reference_number: string;
    amount_approved: number;
    status: string;
    disbursed_at: string | null;
  }>;
}

export default function SectorDetail() {
  const { sectorName } = useParams<{ sectorName: string }>();
  const [data, setData] = useState<SectorDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [showLoans, setShowLoans] = useState(false);

  useEffect(() => {
    if (sectorName) loadData();
  }, [sectorName]);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await sectorApi.getSectorDetail(decodeURIComponent(sectorName!));
      setData(res.data);
    } catch (err) {
      console.error('Failed to load sector detail', err);
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

  if (!data) return <div className="text-center py-20 text-[var(--color-text-muted)]">Sector not found</div>;

  const dpdBarData = [
    { bucket: 'Current', count: data.current_count, fill: '#22C55E' },
    { bucket: '30 DPD', count: data.dpd_30.count, fill: '#EAB308' },
    { bucket: '60 DPD', count: data.dpd_60.count, fill: '#F97316' },
    { bucket: '90+ DPD', count: data.dpd_90.count, fill: '#EF4444' },
  ];

  const rollRateData = [
    { transition: 'Current → 30 DPD', rate: (data.roll_rates.current_to_30 * 100).toFixed(1), fill: '#EAB308' },
    { transition: '30 → 60 DPD', rate: (data.roll_rates.dpd30_to_60 * 100).toFixed(1), fill: '#F97316' },
    { transition: '60 → 90+ DPD', rate: (data.roll_rates.dpd60_to_90 * 100).toFixed(1), fill: '#EF4444' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          to="/backoffice/sector-analysis"
          className="p-2 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]"
        >
          <ArrowLeft size={20} />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-[var(--color-text)]">{data.sector}</h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">Sector Risk Profile & Performance</p>
        </div>
        <div className="flex items-center gap-2">
          {data.policy?.on_watchlist && (
            <span className="px-3 py-1 rounded-full text-xs bg-yellow-500/20 text-yellow-400 flex items-center gap-1">
              <Eye size={12} /> Watchlist
            </span>
          )}
          {data.policy?.origination_paused && (
            <span className="px-3 py-1 rounded-full text-xs bg-red-500/20 text-red-400 flex items-center gap-1">
              <PauseCircle size={12} /> Paused
            </span>
          )}
          {data.policy && (
            <span className={`px-3 py-1 rounded-full text-xs capitalize ${
              data.policy.risk_rating === 'critical' ? 'bg-red-500/20 text-red-400' :
              data.policy.risk_rating === 'very_high' ? 'bg-orange-500/20 text-orange-400' :
              data.policy.risk_rating === 'high' ? 'bg-yellow-500/20 text-yellow-400' :
              data.policy.risk_rating === 'medium' ? 'bg-blue-500/20 text-blue-400' :
              'bg-green-500/20 text-green-400'
            }`}>
              <Shield size={12} className="inline mr-1" />
              {data.policy.risk_rating?.replace('_', ' ')} risk
            </span>
          )}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <Card className="p-4">
          <div className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Outstanding</div>
          <div className="text-lg font-bold text-[var(--color-text)] mt-1">{fmt(data.total_outstanding)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Active Loans</div>
          <div className="text-lg font-bold text-[var(--color-text)] mt-1">{data.loan_count}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Avg Loan Size</div>
          <div className="text-lg font-bold text-[var(--color-text)] mt-1">{fmt(data.avg_loan_size)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Exposure</div>
          <div className="text-lg font-bold text-[var(--color-text)] mt-1">{data.exposure_pct}%</div>
          {data.policy?.exposure_cap_pct && (
            <div className="text-xs text-[var(--color-text-muted)]">Cap: {data.policy.exposure_cap_pct}%</div>
          )}
        </Card>
        <Card className="p-4">
          <div className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Delinquency</div>
          <div className="text-lg font-bold mt-1" style={{ color: data.delinquency_rate > 10 ? '#EF4444' : data.delinquency_rate > 5 ? '#EAB308' : '#22C55E' }}>
            {data.delinquency_rate}%
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">NPL Ratio</div>
          <div className="text-lg font-bold mt-1" style={{ color: data.npl_ratio > 5 ? '#EF4444' : data.npl_ratio > 2 ? '#EAB308' : '#22C55E' }}>
            {data.npl_ratio}%
          </div>
        </Card>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Delinquency Distribution */}
        <Card className="p-6">
          <h2 className="font-semibold text-[var(--color-text)] mb-4">
            <AlertTriangle size={18} className="inline mr-2 text-yellow-400" />
            Delinquency Distribution
          </h2>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={dpdBarData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="bucket" stroke="var(--color-text-muted)" tick={{ fontSize: 12 }} />
              <YAxis stroke="var(--color-text-muted)" />
              <Tooltip contentStyle={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '8px' }} />
              <Bar dataKey="count" name="Loans" radius={[4, 4, 0, 0]}>
                {dpdBarData.map((entry, idx) => (
                  <Cell key={idx} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-3 gap-4 mt-4 text-center text-xs">
            <div className="p-2 rounded-lg bg-yellow-500/10">
              <div className="font-bold text-yellow-400">{fmt(data.dpd_30.amount)}</div>
              <div className="text-[var(--color-text-muted)]">30 DPD Amount</div>
            </div>
            <div className="p-2 rounded-lg bg-orange-500/10">
              <div className="font-bold text-orange-400">{fmt(data.dpd_60.amount)}</div>
              <div className="text-[var(--color-text-muted)]">60 DPD Amount</div>
            </div>
            <div className="p-2 rounded-lg bg-red-500/10">
              <div className="font-bold text-red-400">{fmt(data.dpd_90.amount)}</div>
              <div className="text-[var(--color-text-muted)]">90+ DPD Amount</div>
            </div>
          </div>
        </Card>

        {/* Roll Rates */}
        <Card className="p-6">
          <h2 className="font-semibold text-[var(--color-text)] mb-4">
            <Activity size={18} className="inline mr-2 text-[var(--color-primary)]" />
            Roll Rate Analysis
          </h2>
          <div className="space-y-4 mt-6">
            {rollRateData.map((rr, idx) => (
              <div key={idx}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm text-[var(--color-text)]">{rr.transition}</span>
                  <span className="text-sm font-bold" style={{ color: rr.fill }}>{rr.rate}%</span>
                </div>
                <div className="w-full h-3 bg-[var(--color-bg)] rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(parseFloat(rr.rate), 100)}%`, backgroundColor: rr.fill }}
                  />
                </div>
              </div>
            ))}
          </div>

          {/* Policy Overlays */}
          {data.policy && (
            <div className="mt-6 p-4 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
              <h3 className="text-sm font-medium text-[var(--color-text)] mb-2">
                <Shield size={14} className="inline mr-1" /> Active Policy
              </h3>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {data.policy.exposure_cap_pct && (
                  <div>
                    <span className="text-[var(--color-text-muted)]">Exposure Cap:</span>{' '}
                    <span className="text-[var(--color-text)]">{data.policy.exposure_cap_pct}%</span>
                  </div>
                )}
                {data.policy.max_loan_amount_override && (
                  <div>
                    <span className="text-[var(--color-text-muted)]">Max Loan:</span>{' '}
                    <span className="text-[var(--color-text)]">{fmt(data.policy.max_loan_amount_override)}</span>
                  </div>
                )}
                {data.policy.min_credit_score_override && (
                  <div>
                    <span className="text-[var(--color-text-muted)]">Min Score:</span>{' '}
                    <span className="text-[var(--color-text)]">{data.policy.min_credit_score_override}</span>
                  </div>
                )}
                {data.policy.max_term_months_override && (
                  <div>
                    <span className="text-[var(--color-text-muted)]">Max Term:</span>{' '}
                    <span className="text-[var(--color-text)]">{data.policy.max_term_months_override} months</span>
                  </div>
                )}
                {data.policy.require_collateral && (
                  <div className="text-yellow-400">Collateral Required</div>
                )}
                {data.policy.require_guarantor && (
                  <div className="text-yellow-400">Guarantor Required</div>
                )}
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* Historical Trend */}
      {data.snapshots.length > 0 && (
        <Card className="p-6">
          <h2 className="font-semibold text-[var(--color-text)] mb-4">
            <TrendingUp size={18} className="inline mr-2 text-[var(--color-primary)]" />
            Historical Trend
          </h2>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={data.snapshots}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis
                dataKey="date"
                stroke="var(--color-text-muted)"
                tick={{ fontSize: 11 }}
                tickFormatter={v => {
                  const d = new Date(v);
                  return `${d.toLocaleString('default', { month: 'short' })} ${d.getFullYear().toString().slice(2)}`;
                }}
              />
              <YAxis yAxisId="left" stroke="var(--color-text-muted)" tickFormatter={v => `${v}%`} />
              <YAxis yAxisId="right" orientation="right" stroke="var(--color-text-muted)" />
              <Tooltip
                contentStyle={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '8px' }}
                labelStyle={{ color: 'var(--color-text)' }}
              />
              <Legend />
              <Area yAxisId="left" type="monotone" dataKey="delinquency_rate" name="Delinquency %" stroke="#EAB308" fill="#EAB30820" strokeWidth={2} />
              <Area yAxisId="left" type="monotone" dataKey="npl_ratio" name="NPL %" stroke="#EF4444" fill="#EF444420" strokeWidth={2} />
              <Area yAxisId="right" type="monotone" dataKey="loan_count" name="Loans" stroke="#0ea5e9" fill="#0ea5e920" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Loan Listings (Drill-down) */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-[var(--color-text)]">
            <FileText size={18} className="inline mr-2 text-[var(--color-primary)]" />
            Loans in {data.sector}
          </h2>
          <button
            onClick={() => setShowLoans(!showLoans)}
            className="text-sm text-[var(--color-primary)] hover:underline"
          >
            {showLoans ? 'Hide' : `Show all (${data.loans.length})`}
          </button>
        </div>
        {showLoans && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-[var(--color-text-muted)] uppercase tracking-wider border-b border-[var(--color-border)]">
                  <th className="pb-3 pr-4">Reference</th>
                  <th className="pb-3 pr-4 text-right">Amount</th>
                  <th className="pb-3 pr-4">Status</th>
                  <th className="pb-3 pr-4">Disbursed</th>
                  <th className="pb-3"></th>
                </tr>
              </thead>
              <tbody>
                {data.loans.map(loan => (
                  <tr key={loan.id} className="border-b border-[var(--color-border)]/50 hover:bg-[var(--color-surface-hover)]">
                    <td className="py-2 pr-4 font-mono text-[var(--color-primary)]">{loan.reference_number}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">{fmt(loan.amount_approved)}</td>
                    <td className="py-2 pr-4">
                      <span className="px-2 py-0.5 rounded-full text-xs bg-green-500/20 text-green-400 capitalize">
                        {loan.status}
                      </span>
                    </td>
                    <td className="py-2 pr-4 text-[var(--color-text-muted)]">
                      {loan.disbursed_at ? new Date(loan.disbursed_at).toLocaleDateString() : '-'}
                    </td>
                    <td className="py-2">
                      <Link to={`/backoffice/review/${loan.id}`} className="text-[var(--color-primary)]">
                        <ChevronRight size={16} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!showLoans && data.loans.length > 0 && (
          <p className="text-sm text-[var(--color-text-muted)]">
            {data.loans.length} loans totaling {fmt(data.total_outstanding)}
          </p>
        )}
      </Card>
    </div>
  );
}
