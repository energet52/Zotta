import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowLeft, Shield, PlusCircle, PauseCircle, Eye,
  CheckCircle, XCircle, Edit2, Trash2, RefreshCw,
  AlertTriangle, Target, Lock, Users, Activity,
} from 'lucide-react';
import Card from '../../../../components/ui/Card';
import { sectorApi } from '../../../../api/endpoints';

const SECTORS = [
  'Banking & Financial Services', 'Hospitality & Tourism', 'Agriculture & Agro-processing',
  'Oil, Gas & Energy', 'Mining & Extractives', 'Telecommunications', 'Retail & Distribution',
  'Real Estate & Construction', 'Manufacturing', 'Transportation & Logistics',
  'Healthcare & Pharmaceuticals', 'Education', 'Government & Public Sector',
  'Utilities (Water & Electricity)', 'Creative Industries & Entertainment', 'Maritime & Shipping',
  'Professional Services', 'Information Technology', 'Insurance', 'Microfinance & Credit Unions',
  'Other', 'Not Applicable', 'MISSING',
];

const RISK_RATINGS = ['low', 'medium', 'high', 'very_high', 'critical'];
const METRICS = [
  { value: 'exposure_pct', label: 'Exposure %' },
  { value: 'delinquency_rate', label: 'Delinquency Rate' },
  { value: 'npl_ratio', label: 'NPL Ratio' },
  { value: 'default_rate', label: 'Default Rate' },
  { value: 'roll_rate_30_60', label: 'Roll Rate 30→60' },
  { value: 'roll_rate_60_90', label: 'Roll Rate 60→90' },
  { value: 'loan_count', label: 'Loan Count' },
  { value: 'total_outstanding', label: 'Total Outstanding' },
];
const OPERATORS = ['>', '>=', '<', '<=', '=='];
const SEVERITIES = ['informational', 'warning', 'critical'];

interface Policy {
  id: number;
  sector: string;
  exposure_cap_pct: number | null;
  exposure_cap_amount: number | null;
  origination_paused: boolean;
  pause_reason: string | null;
  pause_effective_date: string | null;
  pause_expiry_date: string | null;
  max_loan_amount_override: number | null;
  min_credit_score_override: number | null;
  max_term_months_override: number | null;
  require_collateral: boolean;
  require_guarantor: boolean;
  risk_rating: string;
  on_watchlist: boolean;
  watchlist_review_frequency: string | null;
  status: string;
  justification: string | null;
  created_by: number;
  approved_by: number | null;
}

interface AlertRule {
  id: number;
  name: string;
  description: string | null;
  sector: string | null;
  metric: string;
  operator: string;
  threshold: number;
  consecutive_months: number;
  severity: string;
  recommended_action: string | null;
  is_active: boolean;
}

interface Alert {
  id: number;
  sector: string;
  severity: string;
  title: string;
  description: string | null;
  metric_name: string | null;
  metric_value: number | null;
  threshold_value: number | null;
  recommended_action: string | null;
  status: string;
  action_notes: string | null;
  created_at: string;
}

type TabType = 'policies' | 'alerts' | 'rules' | 'stress';

export default function SectorPolicies() {
  const [tab, setTab] = useState<TabType>('policies');
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [alertRules, setAlertRules] = useState<AlertRule[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<Policy | null>(null);

  // Policy form state
  const [form, setForm] = useState({
    sector: '', exposure_cap_pct: '', exposure_cap_amount: '',
    origination_paused: false, pause_effective_date: '', pause_expiry_date: '', pause_reason: '',
    max_loan_amount_override: '', min_credit_score_override: '', max_term_months_override: '',
    require_collateral: false, require_guarantor: false,
    risk_rating: 'medium', on_watchlist: false, watchlist_review_frequency: '',
    justification: '',
  });

  // Alert rule form state
  const [ruleForm, setRuleForm] = useState({
    name: '', description: '', sector: '', metric: 'exposure_pct',
    operator: '>', threshold: '', consecutive_months: '1',
    severity: 'warning', recommended_action: '',
  });

  // Stress test state
  const [stressName, setStressName] = useState('Custom Scenario');
  const [stressShocks, setStressShocks] = useState<Record<string, { default_rate_multiplier: number; exposure_change_pct: number }>>({});
  const [stressResult, setStressResult] = useState<any>(null);

  useEffect(() => {
    loadAll();
  }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [polRes, ruleRes, alertRes] = await Promise.all([
        sectorApi.getPolicies(),
        sectorApi.getAlertRules(),
        sectorApi.getAlerts(),
      ]);
      setPolicies(polRes.data);
      setAlertRules(ruleRes.data);
      setAlerts(alertRes.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSavePolicy = async () => {
    const payload: Record<string, unknown> = {
      sector: form.sector,
      origination_paused: form.origination_paused,
      require_collateral: form.require_collateral,
      require_guarantor: form.require_guarantor,
      risk_rating: form.risk_rating,
      on_watchlist: form.on_watchlist,
      justification: form.justification || null,
    };
    if (form.exposure_cap_pct) payload.exposure_cap_pct = parseFloat(form.exposure_cap_pct);
    if (form.exposure_cap_amount) payload.exposure_cap_amount = parseFloat(form.exposure_cap_amount);
    if (form.pause_effective_date) payload.pause_effective_date = form.pause_effective_date;
    if (form.pause_expiry_date) payload.pause_expiry_date = form.pause_expiry_date;
    if (form.pause_reason) payload.pause_reason = form.pause_reason;
    if (form.max_loan_amount_override) payload.max_loan_amount_override = parseFloat(form.max_loan_amount_override);
    if (form.min_credit_score_override) payload.min_credit_score_override = parseInt(form.min_credit_score_override);
    if (form.max_term_months_override) payload.max_term_months_override = parseInt(form.max_term_months_override);
    if (form.watchlist_review_frequency) payload.watchlist_review_frequency = form.watchlist_review_frequency;

    try {
      if (editingPolicy) {
        await sectorApi.updatePolicy(editingPolicy.id, payload);
      } else {
        await sectorApi.createPolicy(payload);
      }
      setShowForm(false);
      setEditingPolicy(null);
      resetForm();
      loadAll();
    } catch (err) {
      console.error(err);
    }
  };

  const resetForm = () => {
    setForm({
      sector: '', exposure_cap_pct: '', exposure_cap_amount: '',
      origination_paused: false, pause_effective_date: '', pause_expiry_date: '', pause_reason: '',
      max_loan_amount_override: '', min_credit_score_override: '', max_term_months_override: '',
      require_collateral: false, require_guarantor: false,
      risk_rating: 'medium', on_watchlist: false, watchlist_review_frequency: '', justification: '',
    });
  };

  const handleEditPolicy = (p: Policy) => {
    setEditingPolicy(p);
    setForm({
      sector: p.sector,
      exposure_cap_pct: p.exposure_cap_pct?.toString() || '',
      exposure_cap_amount: p.exposure_cap_amount?.toString() || '',
      origination_paused: p.origination_paused,
      pause_effective_date: p.pause_effective_date || '',
      pause_expiry_date: p.pause_expiry_date || '',
      pause_reason: p.pause_reason || '',
      max_loan_amount_override: p.max_loan_amount_override?.toString() || '',
      min_credit_score_override: p.min_credit_score_override?.toString() || '',
      max_term_months_override: p.max_term_months_override?.toString() || '',
      require_collateral: p.require_collateral,
      require_guarantor: p.require_guarantor,
      risk_rating: p.risk_rating,
      on_watchlist: p.on_watchlist,
      watchlist_review_frequency: p.watchlist_review_frequency || '',
      justification: p.justification || '',
    });
    setShowForm(true);
  };

  const handleApprovePolicy = async (id: number) => {
    try {
      await sectorApi.approvePolicy(id);
      loadAll();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Approval failed');
    }
  };

  const handleArchivePolicy = async (id: number) => {
    if (!confirm('Archive this policy?')) return;
    try {
      await sectorApi.archivePolicy(id);
      loadAll();
    } catch (err) {
      console.error(err);
    }
  };

  const handleSaveRule = async () => {
    try {
      await sectorApi.createAlertRule({
        name: ruleForm.name,
        description: ruleForm.description || null,
        sector: ruleForm.sector || null,
        metric: ruleForm.metric,
        operator: ruleForm.operator,
        threshold: parseFloat(ruleForm.threshold),
        consecutive_months: parseInt(ruleForm.consecutive_months),
        severity: ruleForm.severity,
        recommended_action: ruleForm.recommended_action || null,
      });
      setShowRuleForm(false);
      setRuleForm({ name: '', description: '', sector: '', metric: 'exposure_pct', operator: '>', threshold: '', consecutive_months: '1', severity: 'warning', recommended_action: '' });
      loadAll();
    } catch (err) {
      console.error(err);
    }
  };

  const handleAcknowledgeAlert = async (id: number) => {
    try {
      await sectorApi.updateAlert(id, { status: 'acknowledged' });
      loadAll();
    } catch (err) {
      console.error(err);
    }
  };

  const handleRunStressTest = async () => {
    try {
      const res = await sectorApi.runStressTest({ name: stressName, shocks: stressShocks });
      setStressResult(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const addStressShock = (sector: string) => {
    setStressShocks(prev => ({
      ...prev,
      [sector]: { default_rate_multiplier: 2.0, exposure_change_pct: 0 },
    }));
  };

  const fmt = (n: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'TTD', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

  const tabs: { key: TabType; label: string; icon: any }[] = [
    { key: 'policies', label: 'Policies', icon: Shield },
    { key: 'alerts', label: 'Alerts', icon: AlertTriangle },
    { key: 'rules', label: 'Alert Rules', icon: Target },
    { key: 'stress', label: 'Stress Test', icon: Activity },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to="/backoffice/sector-analysis" className="p-2 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]">
          <ArrowLeft size={20} />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">Sector Policies & Alerts</h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">Manage concentration limits, origination gates, and alert rules</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-[var(--color-surface)] p-1 rounded-lg border border-[var(--color-border)] w-fit">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm transition-colors ${
              tab === t.key
                ? 'bg-[var(--color-primary)] text-white'
                : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
            }`}
          >
            <t.icon size={16} />
            {t.label}
            {t.key === 'alerts' && alerts.filter(a => a.status === 'new').length > 0 && (
              <span className="bg-red-500 text-white text-xs rounded-full px-1.5 py-0.5 min-w-[20px] text-center">
                {alerts.filter(a => a.status === 'new').length}
              </span>
            )}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48"><RefreshCw className="animate-spin text-[var(--color-primary)]" size={28} /></div>
      ) : (
        <>
          {/* ═══ POLICIES TAB ═══ */}
          {tab === 'policies' && (
            <div className="space-y-4">
              <div className="flex justify-end">
                <button onClick={() => { resetForm(); setEditingPolicy(null); setShowForm(true); }} className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary)]/90">
                  <PlusCircle size={16} /> New Policy
                </button>
              </div>

              {showForm && (
                <Card className="p-6 border-2 border-[var(--color-primary)]/30">
                  <h3 className="font-semibold text-[var(--color-text)] mb-4">{editingPolicy ? 'Edit Policy' : 'New Sector Policy'}</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-xs text-[var(--color-text-muted)] mb-1">Sector *</label>
                      <select value={form.sector} onChange={e => setForm(f => ({ ...f, sector: e.target.value }))} className="w-full h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm" disabled={!!editingPolicy}>
                        <option value="">Select sector...</option>
                        {SECTORS.map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-[var(--color-text-muted)] mb-1">Exposure Cap (%)</label>
                      <input type="number" step="0.1" value={form.exposure_cap_pct} onChange={e => setForm(f => ({ ...f, exposure_cap_pct: e.target.value }))} className="w-full h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm" placeholder="e.g. 15" />
                    </div>
                    <div>
                      <label className="block text-xs text-[var(--color-text-muted)] mb-1">Risk Rating</label>
                      <select value={form.risk_rating} onChange={e => setForm(f => ({ ...f, risk_rating: e.target.value }))} className="w-full h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm">
                        {RISK_RATINGS.map(r => <option key={r} value={r}>{r.replace('_', ' ')}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-[var(--color-text-muted)] mb-1">Max Loan Amount Override</label>
                      <input type="number" value={form.max_loan_amount_override} onChange={e => setForm(f => ({ ...f, max_loan_amount_override: e.target.value }))} className="w-full h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm" />
                    </div>
                    <div>
                      <label className="block text-xs text-[var(--color-text-muted)] mb-1">Min Credit Score Override</label>
                      <input type="number" value={form.min_credit_score_override} onChange={e => setForm(f => ({ ...f, min_credit_score_override: e.target.value }))} className="w-full h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm" />
                    </div>
                    <div>
                      <label className="block text-xs text-[var(--color-text-muted)] mb-1">Max Term Override (months)</label>
                      <input type="number" value={form.max_term_months_override} onChange={e => setForm(f => ({ ...f, max_term_months_override: e.target.value }))} className="w-full h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm" />
                    </div>

                    <div className="flex items-center gap-6 col-span-full">
                      <label className="flex items-center gap-2 text-sm text-[var(--color-text)]">
                        <input type="checkbox" checked={form.origination_paused} onChange={e => setForm(f => ({ ...f, origination_paused: e.target.checked }))} className="rounded" />
                        <PauseCircle size={16} className="text-red-400" /> Pause Origination
                      </label>
                      <label className="flex items-center gap-2 text-sm text-[var(--color-text)]">
                        <input type="checkbox" checked={form.on_watchlist} onChange={e => setForm(f => ({ ...f, on_watchlist: e.target.checked }))} className="rounded" />
                        <Eye size={16} className="text-yellow-400" /> Watchlist
                      </label>
                      <label className="flex items-center gap-2 text-sm text-[var(--color-text)]">
                        <input type="checkbox" checked={form.require_collateral} onChange={e => setForm(f => ({ ...f, require_collateral: e.target.checked }))} className="rounded" />
                        <Lock size={16} /> Require Collateral
                      </label>
                      <label className="flex items-center gap-2 text-sm text-[var(--color-text)]">
                        <input type="checkbox" checked={form.require_guarantor} onChange={e => setForm(f => ({ ...f, require_guarantor: e.target.checked }))} className="rounded" />
                        <Users size={16} /> Require Guarantor
                      </label>
                    </div>

                    {form.origination_paused && (
                      <>
                        <div>
                          <label className="block text-xs text-[var(--color-text-muted)] mb-1">Pause Start</label>
                          <input type="date" value={form.pause_effective_date} onChange={e => setForm(f => ({ ...f, pause_effective_date: e.target.value }))} className="w-full h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm" />
                        </div>
                        <div>
                          <label className="block text-xs text-[var(--color-text-muted)] mb-1">Pause End</label>
                          <input type="date" value={form.pause_expiry_date} onChange={e => setForm(f => ({ ...f, pause_expiry_date: e.target.value }))} className="w-full h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm" />
                        </div>
                        <div>
                          <label className="block text-xs text-[var(--color-text-muted)] mb-1">Pause Reason</label>
                          <input type="text" value={form.pause_reason} onChange={e => setForm(f => ({ ...f, pause_reason: e.target.value }))} className="w-full h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm" />
                        </div>
                      </>
                    )}

                    <div className="col-span-full">
                      <label className="block text-xs text-[var(--color-text-muted)] mb-1">Justification</label>
                      <textarea value={form.justification} onChange={e => setForm(f => ({ ...f, justification: e.target.value }))} rows={2} className="w-full h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm" />
                    </div>
                  </div>

                  <div className="flex justify-end gap-3 mt-4">
                    <button onClick={() => { setShowForm(false); setEditingPolicy(null); }} className="px-4 py-2 text-sm rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)]">Cancel</button>
                    <button onClick={handleSavePolicy} disabled={!form.sector} className="px-4 py-2 text-sm rounded-lg bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary)]/90 disabled:opacity-50">
                      {editingPolicy ? 'Update Policy' : 'Create Policy'}
                    </button>
                  </div>
                </Card>
              )}

              {/* Policies Table */}
              <Card className="p-0 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-[var(--color-text-muted)] uppercase tracking-wider bg-[var(--color-bg)]">
                      <th className="px-4 py-3">Sector</th>
                      <th className="px-4 py-3">Risk</th>
                      <th className="px-4 py-3 text-center">Cap %</th>
                      <th className="px-4 py-3 text-center">Status</th>
                      <th className="px-4 py-3 text-center">Flags</th>
                      <th className="px-4 py-3">Overlays</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {policies.length === 0 ? (
                      <tr><td colSpan={7} className="px-4 py-8 text-center text-[var(--color-text-muted)]">No policies defined yet</td></tr>
                    ) : policies.map(p => (
                      <tr key={p.id} className="border-t border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]">
                        <td className="px-4 py-3 font-medium text-[var(--color-text)]">{p.sector}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 rounded-full text-xs capitalize ${
                            p.risk_rating === 'critical' ? 'bg-red-500/20 text-red-400' :
                            p.risk_rating === 'very_high' ? 'bg-orange-500/20 text-orange-400' :
                            p.risk_rating === 'high' ? 'bg-yellow-500/20 text-yellow-400' :
                            p.risk_rating === 'medium' ? 'bg-blue-500/20 text-blue-400' :
                            'bg-green-500/20 text-green-400'
                          }`}>{p.risk_rating?.replace('_', ' ')}</span>
                        </td>
                        <td className="px-4 py-3 text-center tabular-nums">{p.exposure_cap_pct ? `${p.exposure_cap_pct}%` : '-'}</td>
                        <td className="px-4 py-3 text-center">
                          <span className={`px-2 py-0.5 rounded-full text-xs ${
                            p.status === 'active' ? 'bg-green-500/20 text-green-400' :
                            p.status === 'pending_approval' ? 'bg-yellow-500/20 text-yellow-400' :
                            'bg-gray-500/20 text-gray-400'
                          }`}>{p.status.replace('_', ' ')}</span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <div className="flex items-center justify-center gap-1">
                            {p.origination_paused && <PauseCircle size={14} className="text-red-400" />}
                            {p.on_watchlist && <Eye size={14} className="text-yellow-400" />}
                            {p.require_collateral && <Lock size={14} className="text-orange-400" />}
                            {p.require_guarantor && <Users size={14} className="text-orange-400" />}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-xs text-[var(--color-text-muted)]">
                          {[
                            p.max_loan_amount_override && `Max $${(p.max_loan_amount_override/1000).toFixed(0)}k`,
                            p.min_credit_score_override && `Min Score ${p.min_credit_score_override}`,
                            p.max_term_months_override && `Max ${p.max_term_months_override}mo`,
                          ].filter(Boolean).join(', ') || '-'}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            {p.status === 'pending_approval' && (
                              <button onClick={() => handleApprovePolicy(p.id)} className="p-1.5 rounded hover:bg-green-500/20 text-green-400" title="Approve">
                                <CheckCircle size={16} />
                              </button>
                            )}
                            <button onClick={() => handleEditPolicy(p)} className="p-1.5 rounded hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]" title="Edit">
                              <Edit2 size={16} />
                            </button>
                            <button onClick={() => handleArchivePolicy(p.id)} className="p-1.5 rounded hover:bg-red-500/20 text-red-400" title="Archive">
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            </div>
          )}

          {/* ═══ ALERTS TAB ═══ */}
          {tab === 'alerts' && (
            <div className="space-y-4">
              <div className="flex justify-end">
                <button onClick={async () => { try { const res = await sectorApi.evaluateAlerts(); alert(`Evaluated: ${res.data.fired_count} alert(s) fired`); loadAll(); } catch (err) { console.error(err); } }} className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg bg-yellow-600 text-white hover:bg-yellow-700">
                  <RefreshCw size={16} /> Evaluate Now
                </button>
              </div>

              <div className="space-y-3">
                {alerts.length === 0 ? (
                  <Card className="p-8 text-center text-[var(--color-text-muted)]">No alerts</Card>
                ) : alerts.map(a => (
                  <Card key={a.id} className="p-4">
                    <div className="flex items-start gap-4">
                      <div className={`w-3 h-3 rounded-full mt-1 flex-shrink-0 ${
                        a.severity === 'critical' ? 'bg-red-500' :
                        a.severity === 'warning' ? 'bg-yellow-500' :
                        'bg-blue-500'
                      }`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-[var(--color-text)]">{a.title}</span>
                          <span className={`px-2 py-0.5 rounded-full text-xs capitalize ${
                            a.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                            a.severity === 'warning' ? 'bg-yellow-500/20 text-yellow-400' :
                            'bg-blue-500/20 text-blue-400'
                          }`}>{a.severity}</span>
                          <span className={`px-2 py-0.5 rounded-full text-xs capitalize ${
                            a.status === 'new' ? 'bg-red-500/20 text-red-400' :
                            a.status === 'acknowledged' ? 'bg-yellow-500/20 text-yellow-400' :
                            'bg-green-500/20 text-green-400'
                          }`}>{a.status}</span>
                        </div>
                        {a.description && <p className="text-sm text-[var(--color-text-muted)]">{a.description}</p>}
                        {a.recommended_action && (
                          <p className="text-xs text-[var(--color-primary)] mt-1">Recommended: {a.recommended_action}</p>
                        )}
                        <div className="text-xs text-[var(--color-text-muted)] mt-1">
                          {a.sector} | {a.created_at ? new Date(a.created_at).toLocaleString() : ''}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Link to={`/backoffice/sector-analysis/${encodeURIComponent(a.sector)}`} className="text-sm text-[var(--color-primary)] hover:underline">
                          View Sector
                        </Link>
                        {a.status === 'new' && (
                          <button onClick={() => handleAcknowledgeAlert(a.id)} className="px-3 py-1 text-xs rounded-lg bg-yellow-600 text-white hover:bg-yellow-700">
                            Acknowledge
                          </button>
                        )}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* ═══ RULES TAB ═══ */}
          {tab === 'rules' && (
            <div className="space-y-4">
              <div className="flex justify-end">
                <button onClick={() => setShowRuleForm(true)} className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary)]/90">
                  <PlusCircle size={16} /> New Rule
                </button>
              </div>

              {showRuleForm && (
                <Card className="p-6 border-2 border-[var(--color-primary)]/30">
                  <h3 className="font-semibold text-[var(--color-text)] mb-4">New Alert Rule</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-xs text-[var(--color-text-muted)] mb-1">Rule Name *</label>
                      <input type="text" value={ruleForm.name} onChange={e => setRuleForm(f => ({ ...f, name: e.target.value }))} className="w-full h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm" placeholder="e.g. High NPL Alert" />
                    </div>
                    <div>
                      <label className="block text-xs text-[var(--color-text-muted)] mb-1">Sector (blank = all)</label>
                      <select value={ruleForm.sector} onChange={e => setRuleForm(f => ({ ...f, sector: e.target.value }))} className="w-full h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm">
                        <option value="">All sectors</option>
                        {SECTORS.map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-[var(--color-text-muted)] mb-1">Metric *</label>
                      <select value={ruleForm.metric} onChange={e => setRuleForm(f => ({ ...f, metric: e.target.value }))} className="w-full h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm">
                        {METRICS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                      </select>
                    </div>
                    <div className="flex gap-2">
                      <div className="w-24">
                        <label className="block text-xs text-[var(--color-text-muted)] mb-1">Operator</label>
                        <select value={ruleForm.operator} onChange={e => setRuleForm(f => ({ ...f, operator: e.target.value }))} className="w-full h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm">
                          {OPERATORS.map(o => <option key={o} value={o}>{o}</option>)}
                        </select>
                      </div>
                      <div className="flex-1">
                        <label className="block text-xs text-[var(--color-text-muted)] mb-1">Threshold *</label>
                        <input type="number" step="0.1" value={ruleForm.threshold} onChange={e => setRuleForm(f => ({ ...f, threshold: e.target.value }))} className="w-full h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm" />
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs text-[var(--color-text-muted)] mb-1">Severity</label>
                      <select value={ruleForm.severity} onChange={e => setRuleForm(f => ({ ...f, severity: e.target.value }))} className="w-full h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm">
                        {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </div>
                    <div className="col-span-full">
                      <label className="block text-xs text-[var(--color-text-muted)] mb-1">Recommended Action</label>
                      <input type="text" value={ruleForm.recommended_action} onChange={e => setRuleForm(f => ({ ...f, recommended_action: e.target.value }))} className="w-full h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm" placeholder="e.g. Review sector policy and consider tightening criteria" />
                    </div>
                  </div>
                  <div className="flex justify-end gap-3 mt-4">
                    <button onClick={() => setShowRuleForm(false)} className="px-4 py-2 text-sm rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)]">Cancel</button>
                    <button onClick={handleSaveRule} disabled={!ruleForm.name || !ruleForm.threshold} className="px-4 py-2 text-sm rounded-lg bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary)]/90 disabled:opacity-50">Create Rule</button>
                  </div>
                </Card>
              )}

              <Card className="p-0 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-[var(--color-text-muted)] uppercase tracking-wider bg-[var(--color-bg)]">
                      <th className="px-4 py-3">Rule</th>
                      <th className="px-4 py-3">Sector</th>
                      <th className="px-4 py-3">Condition</th>
                      <th className="px-4 py-3">Severity</th>
                      <th className="px-4 py-3 text-center">Active</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {alertRules.length === 0 ? (
                      <tr><td colSpan={6} className="px-4 py-8 text-center text-[var(--color-text-muted)]">No alert rules defined</td></tr>
                    ) : alertRules.map(r => (
                      <tr key={r.id} className="border-t border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]">
                        <td className="px-4 py-3">
                          <div className="font-medium text-[var(--color-text)]">{r.name}</div>
                          {r.description && <div className="text-xs text-[var(--color-text-muted)]">{r.description}</div>}
                        </td>
                        <td className="px-4 py-3 text-[var(--color-text-muted)]">{r.sector || 'All'}</td>
                        <td className="px-4 py-3 font-mono text-xs text-[var(--color-text)]">{r.metric} {r.operator} {r.threshold}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 rounded-full text-xs capitalize ${
                            r.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                            r.severity === 'warning' ? 'bg-yellow-500/20 text-yellow-400' :
                            'bg-blue-500/20 text-blue-400'
                          }`}>{r.severity}</span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          {r.is_active ? <CheckCircle size={16} className="text-green-400 mx-auto" /> : <XCircle size={16} className="text-red-400 mx-auto" />}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button onClick={async () => { await sectorApi.deleteAlertRule(r.id); loadAll(); }} className="p-1.5 rounded hover:bg-red-500/20 text-red-400">
                            <Trash2 size={16} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            </div>
          )}

          {/* ═══ STRESS TEST TAB ═══ */}
          {tab === 'stress' && (
            <div className="space-y-4">
              <Card className="p-6">
                <h3 className="font-semibold text-[var(--color-text)] mb-4">What-If Scenario Builder</h3>
                <div className="flex items-center gap-4 mb-4">
                  <div>
                    <label className="block text-xs text-[var(--color-text-muted)] mb-1">Scenario Name</label>
                    <input type="text" value={stressName} onChange={e => setStressName(e.target.value)} className="h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm w-64" />
                  </div>
                  <div>
                    <label className="block text-xs text-[var(--color-text-muted)] mb-1">Add Sector Shock</label>
                    <select onChange={e => { if (e.target.value) { addStressShock(e.target.value); e.target.value = ''; } }} className="h-[38px] px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] text-sm w-64">
                      <option value="">Select sector...</option>
                      {SECTORS.filter(s => !stressShocks[s]).map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                </div>

                {Object.entries(stressShocks).length > 0 && (
                  <div className="space-y-3 mb-4">
                    {Object.entries(stressShocks).map(([sector, shock]) => (
                      <div key={sector} className="flex items-center gap-4 p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
                        <span className="text-sm font-medium text-[var(--color-text)] w-48 truncate">{sector}</span>
                        <div>
                          <label className="text-xs text-[var(--color-text-muted)]">Default Rate Multiplier</label>
                          <input type="number" step="0.1" value={shock.default_rate_multiplier} onChange={e => setStressShocks(prev => ({ ...prev, [sector]: { ...prev[sector], default_rate_multiplier: parseFloat(e.target.value) || 1 } }))} className="w-24 px-2 py-1 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text)] text-sm ml-2" />
                        </div>
                        <div>
                          <label className="text-xs text-[var(--color-text-muted)]">Exposure Change %</label>
                          <input type="number" value={shock.exposure_change_pct} onChange={e => setStressShocks(prev => ({ ...prev, [sector]: { ...prev[sector], exposure_change_pct: parseFloat(e.target.value) || 0 } }))} className="w-24 px-2 py-1 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text)] text-sm ml-2" />
                        </div>
                        <button onClick={() => setStressShocks(prev => { const n = { ...prev }; delete n[sector]; return n; })} className="text-red-400 hover:text-red-300 p-1">
                          <XCircle size={16} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Pre-built templates */}
                <div className="flex gap-2 mb-4">
                  <span className="text-xs text-[var(--color-text-muted)] pt-1">Templates:</span>
                  <button onClick={() => { setStressName('Hurricane / Natural Disaster'); setStressShocks({ 'Hospitality & Tourism': { default_rate_multiplier: 3.0, exposure_change_pct: -20 }, 'Agriculture & Agro-processing': { default_rate_multiplier: 2.5, exposure_change_pct: -15 }, 'Real Estate & Construction': { default_rate_multiplier: 2.0, exposure_change_pct: -10 } }); }} className="px-3 py-1 text-xs rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]">Hurricane</button>
                  <button onClick={() => { setStressName('Commodity Price Crash'); setStressShocks({ 'Oil, Gas & Energy': { default_rate_multiplier: 3.0, exposure_change_pct: -25 }, 'Mining & Extractives': { default_rate_multiplier: 2.5, exposure_change_pct: -20 } }); }} className="px-3 py-1 text-xs rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]">Commodity Crash</button>
                  <button onClick={() => { setStressName('Tourism Downturn'); setStressShocks({ 'Hospitality & Tourism': { default_rate_multiplier: 2.5, exposure_change_pct: -30 }, 'Transportation & Logistics': { default_rate_multiplier: 1.8, exposure_change_pct: -10 }, 'Retail & Distribution': { default_rate_multiplier: 1.5, exposure_change_pct: -5 } }); }} className="px-3 py-1 text-xs rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]">Tourism Downturn</button>
                  <button onClick={() => { setStressName('Pandemic Scenario'); setStressShocks(Object.fromEntries(SECTORS.slice(0, 20).map(s => [s, { default_rate_multiplier: 1.8, exposure_change_pct: -5 }]))); }} className="px-3 py-1 text-xs rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]">Pandemic</button>
                </div>

                <button onClick={handleRunStressTest} disabled={Object.keys(stressShocks).length === 0} className="px-6 py-2 text-sm rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50">
                  Run Stress Test
                </button>
              </Card>

              {stressResult && (
                <Card className="p-6">
                  <h3 className="font-semibold text-[var(--color-text)] mb-2">Results: {stressResult.scenario_name}</h3>
                  <div className="grid grid-cols-3 gap-4 mb-4">
                    <div className="p-3 rounded-lg bg-[var(--color-bg)]">
                      <div className="text-xs text-[var(--color-text-muted)]">Total Portfolio</div>
                      <div className="text-lg font-bold text-[var(--color-text)]">{fmt(stressResult.total_portfolio)}</div>
                    </div>
                    <div className="p-3 rounded-lg bg-red-500/10">
                      <div className="text-xs text-red-400">Expected Loss</div>
                      <div className="text-lg font-bold text-red-400">{fmt(stressResult.total_expected_loss)}</div>
                    </div>
                    <div className="p-3 rounded-lg bg-red-500/10">
                      <div className="text-xs text-red-400">Impact (% of Portfolio)</div>
                      <div className="text-lg font-bold text-red-400">{stressResult.impact_pct_of_portfolio}%</div>
                    </div>
                  </div>

                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs text-[var(--color-text-muted)] uppercase border-b border-[var(--color-border)]">
                        <th className="pb-2 pr-4">Sector</th>
                        <th className="pb-2 pr-4 text-right">Base Outstanding</th>
                        <th className="pb-2 pr-4 text-right">Stressed Outstanding</th>
                        <th className="pb-2 pr-4 text-right">Base Default %</th>
                        <th className="pb-2 pr-4 text-right">Stressed Default %</th>
                        <th className="pb-2 pr-4 text-right">Expected Loss</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stressResult.sector_results
                        .filter((r: any) => r.expected_loss > 0)
                        .sort((a: any, b: any) => b.expected_loss - a.expected_loss)
                        .map((r: any, idx: number) => (
                          <tr key={idx} className="border-t border-[var(--color-border)]/50">
                            <td className="py-2 pr-4 text-[var(--color-text)]">{r.sector}</td>
                            <td className="py-2 pr-4 text-right tabular-nums">{fmt(r.base_outstanding)}</td>
                            <td className="py-2 pr-4 text-right tabular-nums">{fmt(r.stressed_outstanding)}</td>
                            <td className="py-2 pr-4 text-right">{r.base_default_rate}%</td>
                            <td className="py-2 pr-4 text-right text-red-400">{r.stressed_default_rate}%</td>
                            <td className="py-2 pr-4 text-right font-medium text-red-400">{fmt(r.expected_loss)}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </Card>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
