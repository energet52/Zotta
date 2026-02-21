import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  TrendingUp, Loader2, RefreshCw, Eye, ThumbsUp, ThumbsDown,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import Badge from '../../../components/ui/Badge';
import { preApprovalApi } from '../../../api/endpoints';

interface Analytics {
  total: number;
  pre_approved: number;
  conditionally_approved: number;
  referred: number;
  declined: number;
  converted: number;
  conversion_rate: number;
  merchant_breakdown: { merchant: string; count: number }[];
  category_breakdown: { category: string; count: number }[];
  daily_volume: { date: string; count: number }[];
}

interface ReferredCase {
  id: number;
  reference_code: string;
  phone: string;
  first_name: string;
  last_name: string;
  national_id: string | null;
  item_description: string | null;
  price: number;
  financing_amount: number | null;
  monthly_income: number;
  monthly_expenses: number;
  existing_loan_payments: number;
  dti_ratio: number | null;
  ndi_amount: number | null;
  outcome_details: any;
  merchant_name: string | null;
  employment_status: string;
  employment_tenure: string | null;
  created_at: string;
}

interface ListItem {
  id: number;
  reference_code: string;
  phone: string;
  first_name: string;
  last_name: string;
  item_description: string | null;
  price: number;
  financing_amount: number | null;
  outcome: string | null;
  status: string;
  merchant_name: string | null;
  created_at: string;
}

export default function PreApprovalDashboard() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<'overview' | 'referred' | 'all'>('overview');
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [referred, setReferred] = useState<ReferredCase[]>([]);
  const [allItems, setAllItems] = useState<ListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [decidingRef, setDecidingRef] = useState<string | null>(null);

  const loadAnalytics = useCallback(() => {
    setLoading(true);
    preApprovalApi.adminAnalytics(days)
      .then(r => setAnalytics(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [days]);

  const loadReferred = useCallback(() => {
    preApprovalApi.adminReferred()
      .then(r => setReferred(r.data || []))
      .catch(() => {});
  }, []);

  const loadAll = useCallback(() => {
    preApprovalApi.adminList({})
      .then(r => setAllItems(r.data || []))
      .catch(() => {});
  }, []);

  useEffect(() => { loadAnalytics(); }, [loadAnalytics]);
  useEffect(() => { if (tab === 'referred') loadReferred(); }, [tab, loadReferred]);
  useEffect(() => { if (tab === 'all') loadAll(); }, [tab, loadAll]);

  const handleDecide = async (ref: string, outcome: 'pre_approved' | 'declined') => {
    setDecidingRef(ref);
    try {
      await preApprovalApi.adminDecide(ref, { outcome });
      loadReferred();
    } catch { /* ignore */ }
    setDecidingRef(null);
  };

  const outcomeBadge = (outcome: string | null, status: string) => {
    if (status === 'expired') return <Badge variant="default">Expired</Badge>;
    if (status === 'converted') return <Badge variant="purple">Converted</Badge>;
    switch (outcome) {
      case 'pre_approved': return <Badge variant="success">Pre-Approved</Badge>;
      case 'conditionally_approved': return <Badge variant="warning">Conditional</Badge>;
      case 'referred': return <Badge variant="info">Referred</Badge>;
      case 'declined': return <Badge variant="danger">Declined</Badge>;
      default: return <Badge variant="default">Pending</Badge>;
    }
  };

  const fmt = (n: number) => n.toLocaleString();
  const fmtCurrency = (n: number) => `TTD ${n.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-[var(--color-text)]">Pre-Approvals</h1>
        <div className="flex items-center gap-2">
          <select value={days} onChange={e => setDays(Number(e.target.value))}
            className="px-3 py-1.5 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)]">
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <Button size="sm" variant="ghost" onClick={loadAnalytics}><RefreshCw size={14} /></Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--color-border)]">
        {[
          { id: 'overview' as const, label: 'Overview' },
          { id: 'referred' as const, label: `Referred (${referred.length || '…'})` },
          { id: 'all' as const, label: 'All Records' },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === t.id ? 'border-[var(--color-primary)] text-[var(--color-primary)]' : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {tab === 'overview' && (
        <>
          {loading ? (
            <div className="flex items-center justify-center h-40 text-[var(--color-text-muted)]">
              <Loader2 className="animate-spin mr-2" size={20} /> Loading analytics...
            </div>
          ) : analytics && (
            <>
              {/* KPI Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                <Card padding="sm">
                  <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Total Checks</p>
                  <p className="text-3xl font-bold text-[var(--color-text)] mt-1">{fmt(analytics.total)}</p>
                </Card>
                <Card padding="sm">
                  <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Pre-Approved</p>
                  <p className="text-3xl font-bold text-[var(--color-success)] mt-1">{fmt(analytics.pre_approved + analytics.conditionally_approved)}</p>
                  <p className="text-xs text-[var(--color-text-muted)]">{analytics.total ? Math.round((analytics.pre_approved + analytics.conditionally_approved) / analytics.total * 100) : 0}% approval rate</p>
                </Card>
                <Card padding="sm">
                  <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Converted</p>
                  <p className="text-3xl font-bold text-[var(--color-primary)] mt-1">{fmt(analytics.converted)}</p>
                  <p className="text-xs text-[var(--color-text-muted)]">{analytics.conversion_rate.toFixed(1)}% conversion</p>
                </Card>
                <Card padding="sm">
                  <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Referred</p>
                  <p className="text-3xl font-bold text-[var(--color-warning)] mt-1">{fmt(analytics.referred)}</p>
                  <p className="text-xs text-[var(--color-text-muted)]">Awaiting review</p>
                </Card>
              </div>

              {/* Conversion Funnel */}
              <Card>
                <h3 className="font-semibold text-[var(--color-text)] mb-4 flex items-center"><TrendingUp size={16} className="mr-2" /> Outcome Breakdown</h3>
                <div className="space-y-2">
                  {[
                    { label: 'Pre-Approved', count: analytics.pre_approved, color: 'var(--color-success)', pct: analytics.total ? analytics.pre_approved / analytics.total * 100 : 0 },
                    { label: 'Conditional', count: analytics.conditionally_approved, color: 'var(--color-warning)', pct: analytics.total ? analytics.conditionally_approved / analytics.total * 100 : 0 },
                    { label: 'Referred', count: analytics.referred, color: 'var(--color-primary)', pct: analytics.total ? analytics.referred / analytics.total * 100 : 0 },
                    { label: 'Declined', count: analytics.declined, color: 'var(--color-danger)', pct: analytics.total ? analytics.declined / analytics.total * 100 : 0 },
                  ].map(item => (
                    <div key={item.label} className="flex items-center gap-3">
                      <span className="text-xs text-[var(--color-text-muted)] w-24">{item.label}</span>
                      <div className="flex-1 bg-[var(--color-bg)] rounded-full h-3">
                        <div className="h-3 rounded-full transition-all" style={{ width: `${Math.max(item.pct, 1)}%`, backgroundColor: item.color }} />
                      </div>
                      <span className="text-xs font-medium text-[var(--color-text)] w-16 text-right">{item.count} ({item.pct.toFixed(0)}%)</span>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Merchant & Category */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <Card>
                  <h3 className="font-semibold text-[var(--color-text)] mb-3">By Merchant</h3>
                  {analytics.merchant_breakdown.length === 0 ? (
                    <p className="text-sm text-[var(--color-text-muted)]">No data</p>
                  ) : (
                    <div className="space-y-2">
                      {analytics.merchant_breakdown.map((m, i) => (
                        <div key={i} className="flex justify-between text-sm">
                          <span className="text-[var(--color-text)]">{m.merchant}</span>
                          <span className="text-[var(--color-text-muted)] font-medium">{m.count}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
                <Card>
                  <h3 className="font-semibold text-[var(--color-text)] mb-3">By Category</h3>
                  {analytics.category_breakdown.length === 0 ? (
                    <p className="text-sm text-[var(--color-text-muted)]">No data</p>
                  ) : (
                    <div className="space-y-2">
                      {analytics.category_breakdown.map((c, i) => (
                        <div key={i} className="flex justify-between text-sm">
                          <span className="text-[var(--color-text)] capitalize">{c.category}</span>
                          <span className="text-[var(--color-text-muted)] font-medium">{c.count}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              </div>

              {/* Daily Volume */}
              {analytics.daily_volume.length > 0 && (
                <Card>
                  <h3 className="font-semibold text-[var(--color-text)] mb-3">Daily Volume</h3>
                  <div className="flex items-end gap-1 h-32">
                    {analytics.daily_volume.map((d, i) => {
                      const maxCount = Math.max(...analytics.daily_volume.map(v => v.count), 1);
                      const height = (d.count / maxCount) * 100;
                      return (
                        <div key={i} className="flex-1 flex flex-col items-center justify-end" title={`${d.date}: ${d.count}`}>
                          <div className="w-full bg-[var(--color-primary)] rounded-t transition-all" style={{ height: `${Math.max(height, 2)}%` }} />
                        </div>
                      );
                    })}
                  </div>
                  <div className="flex justify-between text-xs text-[var(--color-text-muted)] mt-1">
                    <span>{analytics.daily_volume[0]?.date}</span>
                    <span>{analytics.daily_volume[analytics.daily_volume.length - 1]?.date}</span>
                  </div>
                </Card>
              )}
            </>
          )}
        </>
      )}

      {/* Referred Tab */}
      {tab === 'referred' && (
        <div className="space-y-3">
          {referred.length === 0 ? (
            <Card>
              <p className="text-center py-8 text-[var(--color-text-muted)]">No referred cases awaiting review</p>
            </Card>
          ) : (
            referred.map(c => (
              <Card key={c.id}>
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h4 className="font-semibold text-[var(--color-text)]">{c.first_name} {c.last_name}</h4>
                    <p className="text-xs text-[var(--color-text-muted)]">{c.reference_code} &middot; {c.phone}</p>
                  </div>
                  <Badge variant="info">Referred</Badge>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-sm mb-3">
                  <div>
                    <span className="text-xs text-[var(--color-text-muted)]">Item</span>
                    <p className="text-[var(--color-text)]">{c.item_description || '—'}</p>
                  </div>
                  <div>
                    <span className="text-xs text-[var(--color-text-muted)]">Financing</span>
                    <p className="font-medium text-[var(--color-text)]">{fmtCurrency(c.financing_amount || c.price)}</p>
                  </div>
                  <div>
                    <span className="text-xs text-[var(--color-text-muted)]">Income</span>
                    <p className="text-[var(--color-text)]">{fmtCurrency(c.monthly_income)}/mo</p>
                  </div>
                  <div>
                    <span className="text-xs text-[var(--color-text-muted)]">DTI</span>
                    <p className={`font-medium ${(c.dti_ratio || 0) > 0.45 ? 'text-[var(--color-danger)]' : 'text-[var(--color-text)]'}`}>
                      {c.dti_ratio ? (c.dti_ratio * 100).toFixed(1) + '%' : '—'}
                    </p>
                  </div>
                </div>

                {c.outcome_details?.reasons?.length > 0 && (
                  <div className="text-xs text-[var(--color-text-muted)] mb-3 p-2 rounded bg-[var(--color-bg)]">
                    <span className="font-medium">Refer reasons:</span> {c.outcome_details.reasons.join('; ')}
                  </div>
                )}

                <div className="flex gap-2 justify-end">
                  <Button size="sm" variant="ghost" onClick={() => navigate(`/backoffice/pre-approvals/${c.reference_code}`)}>
                    <Eye size={14} className="mr-1" /> Details
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handleDecide(c.reference_code, 'declined')}
                    isLoading={decidingRef === c.reference_code} disabled={!!decidingRef}>
                    <ThumbsDown size={14} className="mr-1" /> Decline
                  </Button>
                  <Button size="sm" onClick={() => handleDecide(c.reference_code, 'pre_approved')}
                    isLoading={decidingRef === c.reference_code} disabled={!!decidingRef}>
                    <ThumbsUp size={14} className="mr-1" /> Approve
                  </Button>
                </div>
              </Card>
            ))
          )}
        </div>
      )}

      {/* All Records Tab */}
      {tab === 'all' && (
        <Card padding="none">
          {allItems.length === 0 ? (
            <p className="text-center py-8 text-[var(--color-text-muted)]">No pre-approval records</p>
          ) : (
            <div className="overflow-x-auto max-w-full">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)]">
                    <th className="text-left py-3 px-4 text-[var(--color-text-muted)] font-medium text-xs uppercase">Ref</th>
                    <th className="text-left py-3 px-4 text-[var(--color-text-muted)] font-medium text-xs uppercase">Name</th>
                    <th className="text-left py-3 px-4 text-[var(--color-text-muted)] font-medium text-xs uppercase">Item</th>
                    <th className="text-left py-3 px-4 text-[var(--color-text-muted)] font-medium text-xs uppercase">Amount</th>
                    <th className="text-left py-3 px-4 text-[var(--color-text-muted)] font-medium text-xs uppercase">Outcome</th>
                    <th className="text-left py-3 px-4 text-[var(--color-text-muted)] font-medium text-xs uppercase">Merchant</th>
                    <th className="text-left py-3 px-4 text-[var(--color-text-muted)] font-medium text-xs uppercase">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {allItems.map(item => (
                    <tr key={item.id} onClick={() => navigate(`/backoffice/pre-approvals/${item.reference_code}`)} className="border-b border-[var(--color-border)]/50 hover:bg-[var(--color-surface-hover)] transition-colors cursor-pointer">
                      <td className="py-3 px-4 font-mono text-xs text-[var(--color-primary)]">{item.reference_code}</td>
                      <td className="py-3 px-4 text-[var(--color-text)]">{item.first_name} {item.last_name}</td>
                      <td className="py-3 px-4 text-[var(--color-text-muted)] max-w-[200px] truncate">{item.item_description || '—'}</td>
                      <td className="py-3 px-4 font-medium text-[var(--color-text)]">{item.financing_amount ? fmtCurrency(item.financing_amount) : fmtCurrency(item.price)}</td>
                      <td className="py-3 px-4">{outcomeBadge(item.outcome, item.status)}</td>
                      <td className="py-3 px-4 text-[var(--color-text-muted)]">{item.merchant_name || '—'}</td>
                      <td className="py-3 px-4 text-[var(--color-text-muted)]">{new Date(item.created_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
