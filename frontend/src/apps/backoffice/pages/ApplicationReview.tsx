import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, Shield, AlertTriangle, CheckCircle, XCircle,
  FileText, Clock, Edit3, Save, X, Send, History, Calculator, Paperclip
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import Badge, { getStatusBadge } from '../../../components/ui/Badge';
import { underwriterApi, paymentsApi } from '../../../api/endpoints';

// ── Types ───────────────────────────────────────
interface Profile {
  id: number;
  user_id: number;
  date_of_birth: string | null;
  national_id: string | null;
  gender: string | null;
  marital_status: string | null;
  address_line1: string | null;
  city: string | null;
  parish: string | null;
  employer_name: string | null;
  job_title: string | null;
  employment_type: string | null;
  years_employed: number | null;
  monthly_income: number | null;
  other_income: number | null;
  monthly_expenses: number | null;
  existing_debt: number | null;
  dependents: number | null;
  id_verified: boolean | null;
  id_verification_status: string | null;
}

interface Decision {
  id: number;
  credit_score: number | null;
  risk_band: string | null;
  engine_outcome: string | null;
  engine_reasons: { reasons?: string[]; dti_ratio?: number; lti_ratio?: number } | null;
  scoring_breakdown: Record<string, number> | null;
  rules_results: {
    rules?: { name: string; passed: boolean; message: string; severity: string }[];
    income_benchmark?: { flagged: boolean; benchmark: Record<string, number>; ratio: number; message: string; match_found: boolean };
    expense_benchmark?: { flagged: boolean; benchmark: Record<string, number>; ratio: number; message: string; match_found: boolean };
  } | null;
  suggested_rate: number | null;
  suggested_amount: number | null;
  underwriter_action: string | null;
  override_reason: string | null;
  final_outcome: string | null;
  created_at: string;
}

interface DocumentInfo {
  id: number;
  document_type: string;
  file_name: string;
  file_size: number;
  status: string;
  created_at: string;
}

interface AuditEntry {
  id: number;
  action: string;
  user_name: string | null;
  old_values: Record<string, any> | null;
  new_values: Record<string, any> | null;
  details: string | null;
  created_at: string;
}

interface ContractInfo {
  signature_data: string | null;
  typed_name: string | null;
  signed_at: string | null;
}

interface FullApp {
  application: any;
  profile: Profile | null;
  documents: DocumentInfo[];
  decisions: Decision[];
  audit_log: AuditEntry[];
  contract: ContractInfo | null;
}

type TabKey = 'details' | 'decision' | 'credit_bureau' | 'schedule' | 'payments' | 'documents' | 'audit';

// ── Helpers ──────────────────────────────────────
function parseApiError(err: any, fallback = 'Operation failed'): string {
  const detail = err?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join('; ');
  }
  if (typeof detail === 'string') return detail;
  return fallback;
}

function formatCurrency(val: number | null | undefined) {
  if (val == null) return '-';
  return `TTD ${Number(val).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function daysSince(dateStr: string | null) {
  if (!dateStr) return '-';
  const diff = Date.now() - new Date(dateStr).getTime();
  return Math.floor(diff / 86400000);
}

function generateAmortization(principal: number, annualRate: number, termMonths: number) {
  const monthlyRate = annualRate / 100 / 12;
  let payment: number;
  if (monthlyRate > 0) {
    payment = principal * (monthlyRate * Math.pow(1 + monthlyRate, termMonths)) / (Math.pow(1 + monthlyRate, termMonths) - 1);
  } else {
    payment = principal / termMonths;
  }

  const schedule = [];
  let balance = principal;
  const startDate = new Date();

  for (let i = 1; i <= termMonths; i++) {
    const interest = balance * monthlyRate;
    const principalPart = payment - interest;
    balance = Math.max(0, balance - principalPart);
    const payDate = new Date(startDate);
    payDate.setMonth(payDate.getMonth() + i);

    schedule.push({
      number: i,
      date: payDate.toLocaleDateString('en-US', { year: 'numeric', month: 'short' }),
      principal: principalPart,
      interest,
      payment,
      balance,
    });
  }
  return { schedule, totalInterest: schedule.reduce((s, r) => s + r.interest, 0), totalPayments: payment * termMonths };
}

// ── Component ────────────────────────────────────
export default function ApplicationReview() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<FullApp | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>('details');

  // Decision form
  const [action, setAction] = useState('');
  const [reason, setReason] = useState('');
  const [approvedAmount, setApprovedAmount] = useState('');
  const [approvedRate, setApprovedRate] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Counterproposal form
  const [showCounterproposal, setShowCounterproposal] = useState(false);
  const [cpAmount, setCpAmount] = useState('');
  const [cpRate, setCpRate] = useState('');
  const [cpTerm, setCpTerm] = useState('');
  const [cpReason, setCpReason] = useState('');

  // Edit mode
  const [editing, setEditing] = useState(false);
  const [editValues, setEditValues] = useState<Record<string, any>>({});

  const loadData = () => {
    if (!id) return;
    setLoading(true);
    underwriterApi.getFullApplication(parseInt(id))
      .then((res) => {
        setData(res.data);
        const d = res.data.decisions?.[0];
        if (d?.suggested_amount) setApprovedAmount(String(d.suggested_amount));
        if (d?.suggested_rate) setApprovedRate(String(d.suggested_rate));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, [id]);

  const handleDecide = async () => {
    if (!action || !reason) { setError('Select action and provide a reason'); return; }
    setSubmitting(true); setError('');
    try {
      await underwriterApi.decide(parseInt(id!), {
        action,
        reason,
        approved_amount: approvedAmount ? parseFloat(approvedAmount) : undefined,
        approved_rate: approvedRate ? parseFloat(approvedRate) : undefined,
      });
      setSuccessMsg('Decision recorded');
      loadData();
    } catch (err: any) {
      setError(parseApiError(err, 'Decision failed'));
    } finally { setSubmitting(false); }
  };

  const handleCounterpropose = async () => {
    if (!cpAmount || !cpRate || !cpTerm || !cpReason) { setError('Fill all counterproposal fields'); return; }
    setSubmitting(true); setError('');
    try {
      await underwriterApi.counterpropose(parseInt(id!), {
        proposed_amount: parseFloat(cpAmount),
        proposed_rate: parseFloat(cpRate),
        proposed_term: parseInt(cpTerm),
        reason: cpReason,
      });
      setSuccessMsg('Counterproposal sent');
      setShowCounterproposal(false);
      loadData();
    } catch (err: any) {
      setError(parseApiError(err, 'Counterproposal failed'));
    } finally { setSubmitting(false); }
  };

  const handleSaveEdit = async () => {
    if (Object.keys(editValues).length === 0) { setEditing(false); return; }
    setSubmitting(true); setError('');
    try {
      await underwriterApi.editApplication(parseInt(id!), editValues);
      setEditing(false);
      setEditValues({});
      setSuccessMsg('Changes saved');
      loadData();
    } catch (err: any) {
      setError(parseApiError(err, 'Edit failed'));
    } finally { setSubmitting(false); }
  };

  if (loading) return <div className="text-center py-12 text-[var(--color-text-muted)]">Loading application...</div>;
  if (!data) return <div className="text-center py-12 text-[var(--color-danger)]">Application not found</div>;

  const app = data.application;
  const profile = data.profile;
  const decision = data.decisions?.[0] || null;

  const riskColors: Record<string, string> = { A: '#34d399', B: '#22d3ee', C: '#fbbf24', D: '#f97316', E: '#f87171' };
  const outcomeColors: Record<string, string> = { auto_approve: '#34d399', auto_decline: '#f87171', manual_review: '#fbbf24' };

  const tabs: { key: TabKey; label: string; icon: any }[] = [
    { key: 'details', label: 'Application Details', icon: FileText },
    { key: 'decision', label: 'Decision Engine', icon: Shield },
    { key: 'credit_bureau', label: 'Credit Bureau', icon: Shield },
    { key: 'schedule', label: 'Repayment Schedule', icon: Calculator },
    { key: 'payments', label: 'Payments', icon: Calculator },
    { key: 'documents', label: 'Documents & Contract', icon: Paperclip },
    { key: 'audit', label: 'Audit History', icon: History },
  ];

  // Amortization
  const amortPrincipal = app.amount_approved || app.proposed_amount || app.amount_requested;
  const amortRate = app.interest_rate || app.proposed_rate || decision?.suggested_rate || 12;
  const amortTerm = app.term_months;
  const amort = amortPrincipal && amortRate && amortTerm
    ? generateAmortization(Number(amortPrincipal), Number(amortRate), amortTerm)
    : null;

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <Link to="/backoffice/applications" className="inline-flex items-center text-sm text-[var(--color-text-muted)] hover:text-[var(--color-primary)] mb-4 transition-colors">
        <ArrowLeft size={16} className="mr-1" /> Back to Queue
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">{app.reference_number}</h1>
          <p className="text-sm text-[var(--color-text-muted)]">Application Review</p>
        </div>
        {getStatusBadge(app.status)}
      </div>

      {successMsg && (
        <div className="mb-4 p-3 rounded-lg bg-[var(--color-success)]/15 text-[var(--color-success)] text-sm flex items-center justify-between">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg('')}><X size={14} /></button>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <Card padding="sm">
          <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider mb-1">Amount Requested</p>
          <p className="text-xl font-bold text-[var(--color-text)]">{formatCurrency(app.amount_requested)}</p>
        </Card>
        <Card padding="sm">
          <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider mb-1">Credit Score</p>
          <p className="text-xl font-bold" style={{ color: riskColors[decision?.risk_band || ''] || 'var(--color-text)' }}>
            {decision?.credit_score || '-'}
          </p>
          {decision?.risk_band && <p className="text-xs mt-0.5" style={{ color: riskColors[decision.risk_band] }}>Band {decision.risk_band}</p>}
        </Card>
        <Card padding="sm">
          <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider mb-1">Engine Outcome</p>
          <p className="text-sm font-bold capitalize" style={{ color: outcomeColors[decision?.engine_outcome || ''] || 'var(--color-text-muted)' }}>
            {decision?.engine_outcome?.replace('_', ' ') || 'Pending'}
          </p>
        </Card>
        <Card padding="sm">
          <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider mb-1">Status</p>
          <div className="mt-1">{getStatusBadge(app.status)}</div>
        </Card>
        <Card padding="sm">
          <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider mb-1">Days Since Submit</p>
          <p className="text-xl font-bold text-[var(--color-text)]">{daysSince(app.submitted_at)}</p>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Main Content (3 cols) */}
        <div className="lg:col-span-3">
          {/* Tab Navigation */}
          <div className="flex space-x-1 mb-4 border-b border-[var(--color-border)] overflow-x-auto">
            {tabs.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`flex items-center space-x-2 px-4 py-2.5 text-sm whitespace-nowrap border-b-2 transition-colors ${
                  activeTab === key
                    ? 'border-[var(--color-primary)] text-[var(--color-primary)] font-medium'
                    : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
                }`}
              >
                <Icon size={15} />
                <span>{label}</span>
              </button>
            ))}
          </div>

          {/* Tab: Application Details */}
          {activeTab === 'details' && (
            <div className="space-y-4">
              <Card>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold text-[var(--color-text)]">Applicant Information</h3>
                  {!editing ? (
                    <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
                      <Edit3 size={14} className="mr-1" /> Edit
                    </Button>
                  ) : (
                    <div className="flex space-x-2">
                      <Button size="sm" variant="primary" onClick={handleSaveEdit} isLoading={submitting}>
                        <Save size={14} className="mr-1" /> Save
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => { setEditing(false); setEditValues({}); }}>
                        Cancel
                      </Button>
                    </div>
                  )}
                </div>

                {/* Personal Info */}
                <h4 className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider mb-3">Personal</h4>
                <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 mb-6 text-sm">
                  <InfoField label="National ID" value={profile?.national_id} />
                  <InfoField label="Date of Birth" value={profile?.date_of_birth} />
                  <InfoField label="Gender" value={profile?.gender} />
                  <InfoField label="Marital Status" value={profile?.marital_status} />
                  <InfoField label="Address" value={profile?.address_line1} />
                  <InfoField label="City" value={profile?.city} />
                  <InfoField label="Parish" value={profile?.parish} />
                  <InfoField label="ID Verified" value={profile?.id_verified ? 'Yes' : 'No'} />
                </div>

                {/* Employment */}
                <h4 className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider mb-3">Employment & Financials</h4>
                <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 mb-6 text-sm">
                  <EditableField label="Employer" field="employer_name" value={profile?.employer_name} editing={editing} editValues={editValues} setEditValues={setEditValues} />
                  <EditableField label="Job Title" field="job_title" value={profile?.job_title} editing={editing} editValues={editValues} setEditValues={setEditValues} />
                  <EditableField label="Employment Type" field="employment_type" value={profile?.employment_type} editing={editing} editValues={editValues} setEditValues={setEditValues} />
                  <EditableField label="Years Employed" field="years_employed" value={profile?.years_employed} editing={editing} editValues={editValues} setEditValues={setEditValues} type="number" />
                  <EditableField label="Monthly Income" field="monthly_income" value={profile?.monthly_income} editing={editing} editValues={editValues} setEditValues={setEditValues} type="number" prefix="TTD" />
                  <InfoField label="Other Income" value={profile?.other_income != null ? formatCurrency(profile.other_income) : '-'} />
                  <EditableField label="Monthly Expenses" field="monthly_expenses" value={profile?.monthly_expenses} editing={editing} editValues={editValues} setEditValues={setEditValues} type="number" prefix="TTD" />
                  <EditableField label="Existing Debt" field="existing_debt" value={profile?.existing_debt} editing={editing} editValues={editValues} setEditValues={setEditValues} type="number" prefix="TTD" />
                  <InfoField label="Dependents" value={profile?.dependents} />
                </div>

                {/* Loan Details */}
                <h4 className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider mb-3">Loan Details</h4>
                <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 text-sm">
                  <InfoField label="Amount Requested" value={formatCurrency(app.amount_requested)} />
                  <EditableField label="Term" field="term_months" value={app.term_months} editing={editing} editValues={editValues} setEditValues={setEditValues} type="number" suffix="months" />
                  <InfoField label="Purpose" value={app.purpose?.replace(/_/g, ' ')} />
                  <InfoField label="Description" value={app.purpose_description || '-'} />
                  <InfoField label="Submitted" value={app.submitted_at ? new Date(app.submitted_at).toLocaleString() : '-'} />
                  {app.amount_approved && <InfoField label="Amount Approved" value={formatCurrency(app.amount_approved)} highlight="success" />}
                  {app.interest_rate && <InfoField label="Interest Rate" value={`${app.interest_rate}%`} />}
                  {app.monthly_payment && <InfoField label="Monthly Payment" value={formatCurrency(app.monthly_payment)} />}
                </div>
              </Card>
            </div>
          )}

          {/* Tab: Decision Engine */}
          {activeTab === 'decision' && decision && (
            <div className="space-y-4">
              {/* Score & Band */}
              <Card>
                <h3 className="font-semibold text-[var(--color-text)] mb-4 flex items-center">
                  <Shield size={18} className="mr-2 text-[var(--color-primary)]" />
                  Score & Risk Assessment
                </h3>
                <div className="grid grid-cols-3 gap-4 mb-6">
                  <div className="text-center p-4 rounded-lg bg-[var(--color-bg)]">
                    <p className="text-4xl font-bold" style={{ color: riskColors[decision.risk_band || ''] || 'var(--color-text)' }}>
                      {decision.credit_score || '-'}
                    </p>
                    <p className="text-xs text-[var(--color-text-muted)] mt-1">Credit Score (300-850)</p>
                  </div>
                  <div className="text-center p-4 rounded-lg bg-[var(--color-bg)]">
                    <Badge variant={decision.risk_band === 'A' || decision.risk_band === 'B' ? 'success' : decision.risk_band === 'C' ? 'warning' : 'danger'}>
                      Band {decision.risk_band || '-'}
                    </Badge>
                    <p className="text-xs text-[var(--color-text-muted)] mt-2">Risk Band</p>
                  </div>
                  <div className="text-center p-4 rounded-lg bg-[var(--color-bg)]">
                    <Badge variant={decision.engine_outcome === 'auto_approve' ? 'success' : decision.engine_outcome === 'auto_decline' ? 'danger' : 'warning'}>
                      {decision.engine_outcome?.replace('_', ' ') || '-'}
                    </Badge>
                    <p className="text-xs text-[var(--color-text-muted)] mt-2">Engine Outcome</p>
                  </div>
                </div>

                {/* Scoring Breakdown */}
                {decision.scoring_breakdown && (
                  <div className="mb-6">
                    <h4 className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider mb-3">Scoring Breakdown</h4>
                    <div className="space-y-2">
                      {Object.entries(decision.scoring_breakdown).map(([key, value]) => (
                        <div key={key} className="flex items-center">
                          <span className="text-xs text-[var(--color-text-muted)] w-36 capitalize">{key.replace(/_/g, ' ')}</span>
                          <div className="flex-1 bg-[var(--color-bg)] rounded-full h-2 mx-2">
                            <div
                              className="h-2 rounded-full transition-all"
                              style={{
                                width: `${Math.min(value, 100)}%`,
                                backgroundColor: value > 70 ? '#34d399' : value > 40 ? '#fbbf24' : '#f87171',
                              }}
                            />
                          </div>
                          <span className="text-xs font-medium text-[var(--color-text)] w-8 text-right">{value}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {decision.suggested_rate && (
                  <div className="grid grid-cols-2 gap-4 p-3 rounded-lg bg-[var(--color-bg)]">
                    <div>
                      <span className="text-xs text-[var(--color-text-muted)]">Suggested Rate</span>
                      <p className="font-bold text-[var(--color-primary)]">{decision.suggested_rate}%</p>
                    </div>
                    <div>
                      <span className="text-xs text-[var(--color-text-muted)]">Max Eligible Amount</span>
                      <p className="font-bold text-[var(--color-primary)]">{formatCurrency(decision.suggested_amount)}</p>
                    </div>
                  </div>
                )}
              </Card>

              {/* Business Rules */}
              <Card>
                <h3 className="font-semibold text-[var(--color-text)] mb-4">Business Rules Assessment</h3>
                {decision.rules_results?.rules && (
                  <div className="space-y-2">
                    {decision.rules_results.rules.map((rule, i) => (
                      <div key={i} className={`flex items-start p-2 rounded-lg text-sm ${
                        !rule.passed ? 'bg-[var(--color-danger)]/10' : 'bg-[var(--color-success)]/5'
                      }`}>
                        {rule.passed ? (
                          <CheckCircle size={16} className="text-[var(--color-success)] mr-2 mt-0.5 flex-shrink-0" />
                        ) : (
                          <XCircle size={16} className="text-[var(--color-danger)] mr-2 mt-0.5 flex-shrink-0" />
                        )}
                        <div className="flex-1">
                          <span className={rule.passed ? 'text-[var(--color-text-muted)]' : 'text-[var(--color-danger)]'}>
                            {rule.message}
                          </span>
                        </div>
                        {!rule.passed && (
                          <Badge variant={rule.severity === 'hard' ? 'danger' : 'warning'} className="ml-2 flex-shrink-0">
                            {rule.severity}
                          </Badge>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              {/* Income/Expense Benchmarks */}
              {(decision.rules_results?.income_benchmark || decision.rules_results?.expense_benchmark) && (
                <Card>
                  <h3 className="font-semibold text-[var(--color-text)] mb-4 flex items-center">
                    <AlertTriangle size={18} className="mr-2 text-[var(--color-warning)]" />
                    Occupation Benchmarks
                  </h3>
                  <p className="text-xs text-[var(--color-text-muted)] mb-4">
                    Comparing stated income/expenses against benchmarks for occupation: <strong className="text-[var(--color-text)]">{profile?.job_title || 'Unknown'}</strong>
                  </p>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {decision.rules_results.income_benchmark && (
                      <BenchmarkBar
                        label="Monthly Income"
                        stated={profile?.monthly_income || 0}
                        benchMin={decision.rules_results.income_benchmark.benchmark?.income_min || 0}
                        benchMax={decision.rules_results.income_benchmark.benchmark?.income_max || 0}
                        flagged={decision.rules_results.income_benchmark.flagged}
                        matchFound={decision.rules_results.income_benchmark.match_found}
                      />
                    )}
                    {decision.rules_results.expense_benchmark && (
                      <BenchmarkBar
                        label="Monthly Expenses"
                        stated={profile?.monthly_expenses || 0}
                        benchMin={decision.rules_results.expense_benchmark.benchmark?.expense_min || 0}
                        benchMax={decision.rules_results.expense_benchmark.benchmark?.expense_max || 0}
                        flagged={decision.rules_results.expense_benchmark.flagged}
                        matchFound={decision.rules_results.expense_benchmark.match_found}
                        inverted
                      />
                    )}
                  </div>
                </Card>
              )}
            </div>
          )}

          {activeTab === 'decision' && !decision && (
            <Card>
              <p className="text-center py-8 text-[var(--color-text-muted)]">No decision engine data available yet.</p>
            </Card>
          )}

          {/* Tab: Repayment Schedule */}
          {activeTab === 'schedule' && (
            <Card>
              <h3 className="font-semibold text-[var(--color-text)] mb-4">Repayment Schedule</h3>
              {amort ? (
                <>
                  <div className="grid grid-cols-3 gap-4 mb-4 p-3 rounded-lg bg-[var(--color-bg)]">
                    <div>
                      <span className="text-xs text-[var(--color-text-muted)]">Total Payments</span>
                      <p className="font-bold text-[var(--color-text)]">{formatCurrency(amort.totalPayments)}</p>
                    </div>
                    <div>
                      <span className="text-xs text-[var(--color-text-muted)]">Total Interest</span>
                      <p className="font-bold text-[var(--color-warning)]">{formatCurrency(amort.totalInterest)}</p>
                    </div>
                    <div>
                      <span className="text-xs text-[var(--color-text-muted)]">Monthly Payment</span>
                      <p className="font-bold text-[var(--color-primary)]">{formatCurrency(amort.schedule[0]?.payment)}</p>
                    </div>
                  </div>
                  <div className="overflow-x-auto max-h-96 overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 bg-[var(--color-surface)]">
                        <tr className="border-b border-[var(--color-border)]">
                          <th className="text-left py-2 px-3 text-xs text-[var(--color-text-muted)] uppercase">#</th>
                          <th className="text-left py-2 px-3 text-xs text-[var(--color-text-muted)] uppercase">Date</th>
                          <th className="text-right py-2 px-3 text-xs text-[var(--color-text-muted)] uppercase">Principal</th>
                          <th className="text-right py-2 px-3 text-xs text-[var(--color-text-muted)] uppercase">Interest</th>
                          <th className="text-right py-2 px-3 text-xs text-[var(--color-text-muted)] uppercase">Payment</th>
                          <th className="text-right py-2 px-3 text-xs text-[var(--color-text-muted)] uppercase">Balance</th>
                        </tr>
                      </thead>
                      <tbody>
                        {amort.schedule.map((row) => (
                          <tr key={row.number} className="border-b border-[var(--color-border)]/30">
                            <td className="py-1.5 px-3 text-[var(--color-text-muted)]">{row.number}</td>
                            <td className="py-1.5 px-3 text-[var(--color-text-muted)]">{row.date}</td>
                            <td className="py-1.5 px-3 text-right text-[var(--color-text)]">{formatCurrency(row.principal)}</td>
                            <td className="py-1.5 px-3 text-right text-[var(--color-warning)]">{formatCurrency(row.interest)}</td>
                            <td className="py-1.5 px-3 text-right text-[var(--color-text)] font-medium">{formatCurrency(row.payment)}</td>
                            <td className="py-1.5 px-3 text-right text-[var(--color-text-muted)]">{formatCurrency(row.balance)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <p className="text-center py-8 text-[var(--color-text-muted)]">No approved amount or rate to calculate schedule.</p>
              )}
            </Card>
          )}

          {/* Tab: Documents & Contract */}
          {activeTab === 'documents' && (
            <div className="space-y-4">
              <Card>
                <h3 className="font-semibold text-[var(--color-text)] mb-4">Uploaded Documents</h3>
                {data.documents.length > 0 ? (
                  <div className="space-y-2">
                    {data.documents.map((doc) => (
                      <div key={doc.id} className="flex items-center justify-between p-3 rounded-lg bg-[var(--color-bg)]">
                        <div className="flex items-center space-x-3">
                          <FileText size={18} className="text-[var(--color-primary)]" />
                          <div>
                            <p className="text-sm font-medium text-[var(--color-text)]">{doc.file_name}</p>
                            <p className="text-xs text-[var(--color-text-muted)] capitalize">{doc.document_type.replace(/_/g, ' ')} &middot; {(doc.file_size / 1024).toFixed(0)} KB</p>
                          </div>
                        </div>
                        {getStatusBadge(doc.status)}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-[var(--color-text-muted)]">No documents uploaded</p>
                )}
              </Card>

              {/* Contract */}
              <Card>
                <h3 className="font-semibold text-[var(--color-text)] mb-4">Signed Contract</h3>
                {data.contract ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <InfoField label="Typed Name" value={data.contract.typed_name} />
                      <InfoField label="Signed At" value={data.contract.signed_at ? new Date(data.contract.signed_at).toLocaleString() : '-'} />
                    </div>
                    {data.contract.signature_data && (
                      <div>
                        <p className="text-xs text-[var(--color-text-muted)] mb-2">Signature:</p>
                        <div className="bg-white rounded-lg p-4 inline-block border border-[var(--color-border)]">
                          <img
                            src={data.contract.signature_data}
                            alt="Signature"
                            className="max-h-24"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-[var(--color-text-muted)]">Contract not yet signed by applicant</p>
                )}
              </Card>
            </div>
          )}

          {/* Tab: Audit History */}
          {activeTab === 'audit' && (
            <Card>
              <h3 className="font-semibold text-[var(--color-text)] mb-4">Change History</h3>
              {data.audit_log.length > 0 ? (
                <div className="space-y-3">
                  {data.audit_log.map((entry) => {
                    const actionColors: Record<string, string> = {
                      assigned: 'var(--color-primary)',
                      underwriter_approve: 'var(--color-success)',
                      underwriter_decline: 'var(--color-danger)',
                      underwriter_refer: 'var(--color-warning)',
                      underwriter_request_info: 'var(--color-warning)',
                      underwriter_edit: 'var(--color-primary)',
                      counterproposal: 'var(--color-purple,#a78bfa)',
                      counterproposal_accepted: 'var(--color-success)',
                      counterproposal_rejected: 'var(--color-danger)',
                      contract_signed: 'var(--color-success)',
                      offer_accepted: 'var(--color-success)',
                      offer_declined: 'var(--color-danger)',
                      decision_engine_run: 'var(--color-cyan,#22d3ee)',
                    };
                    const color = actionColors[entry.action] || 'var(--color-text-muted)';

                    return (
                      <div key={entry.id} className="p-3 rounded-lg bg-[var(--color-bg)] border-l-2" style={{ borderLeftColor: color }}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-medium capitalize" style={{ color }}>
                            {entry.action.replace(/_/g, ' ')}
                          </span>
                          <span className="text-xs text-[var(--color-text-muted)]">
                            {new Date(entry.created_at).toLocaleString()}
                          </span>
                        </div>
                        <p className="text-xs text-[var(--color-text-muted)]">
                          by {entry.user_name || 'System'}
                        </p>
                        {entry.old_values && Object.keys(entry.old_values).length > 0 && (
                          <div className="mt-2 text-xs">
                            <p className="text-[var(--color-text-muted)] mb-1">Changes:</p>
                            {Object.entries(entry.new_values || {}).map(([k, v]) => (
                              <div key={k} className="flex items-center space-x-2">
                                <span className="text-[var(--color-text-muted)] capitalize">{k.replace(/_/g, ' ')}:</span>
                                {entry.old_values?.[k] != null && (
                                  <span className="text-[var(--color-danger)] line-through">{String(entry.old_values[k])}</span>
                                )}
                                <span className="text-[var(--color-success)]">{String(v)}</span>
                              </div>
                            ))}
                          </div>
                        )}
                        {entry.details && (
                          <p className="mt-1 text-xs text-[var(--color-text-muted)] italic">{entry.details}</p>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-sm text-[var(--color-text-muted)]">No audit history for this application.</p>
              )}
            </Card>
          )}

          {/* Tab: Credit Bureau */}
          {activeTab === 'credit_bureau' && <CreditBureauTab applicationId={parseInt(id!)} />}

          {/* Tab: Payments */}
          {activeTab === 'payments' && <PaymentsTab applicationId={parseInt(id!)} />}
        </div>

        {/* Right Sidebar - Decision Panel */}
        <div className="space-y-4">
          <Card>
            <h3 className="font-semibold text-[var(--color-text)] mb-4">Underwriter Decision</h3>

            {error && <div className="mb-3 p-2 rounded-lg bg-[var(--color-danger)]/15 text-[var(--color-danger)] text-xs">{error}</div>}

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-2">Action</label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { value: 'approve', label: 'Approve', variant: 'success' },
                    { value: 'decline', label: 'Decline', variant: 'danger' },
                    { value: 'refer', label: 'Refer', variant: 'warning' },
                    { value: 'request_info', label: 'Request Info', variant: 'info' },
                  ].map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => setAction(opt.value)}
                      className={`p-2 rounded-lg border text-xs font-medium transition-all ${
                        action === opt.value
                          ? `border-[var(--color-${opt.variant === 'info' ? 'primary' : opt.variant})] bg-[var(--color-${opt.variant === 'info' ? 'primary' : opt.variant})]/15 text-[var(--color-${opt.variant === 'info' ? 'primary' : opt.variant})]`
                          : 'border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-text-muted)]'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              {action === 'approve' && (
                <div className="space-y-2">
                  <input
                    type="number"
                    placeholder="Approved Amount (TTD)"
                    value={approvedAmount}
                    onChange={(e) => setApprovedAmount(e.target.value)}
                    className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                  />
                  <input
                    type="number"
                    placeholder="Interest Rate (%)"
                    value={approvedRate}
                    onChange={(e) => setApprovedRate(e.target.value)}
                    className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                    step="0.1"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Reason / Notes</label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                  placeholder="Decision rationale..."
                />
              </div>

              <Button
                className="w-full"
                onClick={handleDecide}
                isLoading={submitting}
                variant={action === 'decline' ? 'danger' : action === 'approve' ? 'success' : 'primary'}
                disabled={!action || !reason}
              >
                Confirm Decision
              </Button>
            </div>
          </Card>

          {/* Counterproposal */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-[var(--color-text)] text-sm">Counterproposal</h3>
              <Button size="sm" variant="ghost" onClick={() => setShowCounterproposal(!showCounterproposal)}>
                <Send size={14} className="mr-1" /> {showCounterproposal ? 'Cancel' : 'Propose'}
              </Button>
            </div>
            <p className="text-xs text-[var(--color-text-muted)] mb-3">
              Propose different terms. Applicant must accept or reject.
            </p>
            {showCounterproposal && (
              <div className="space-y-2">
                <input
                  type="number"
                  placeholder="Proposed Amount (TTD)"
                  value={cpAmount}
                  onChange={(e) => setCpAmount(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                />
                <input
                  type="number"
                  placeholder="Proposed Rate (%)"
                  value={cpRate}
                  onChange={(e) => setCpRate(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                  step="0.1"
                />
                <input
                  type="number"
                  placeholder="Proposed Term (months)"
                  value={cpTerm}
                  onChange={(e) => setCpTerm(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                />
                <textarea
                  placeholder="Reason for counterproposal..."
                  value={cpReason}
                  onChange={(e) => setCpReason(e.target.value)}
                  rows={2}
                  className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                />
                <Button className="w-full" variant="warning" onClick={handleCounterpropose} isLoading={submitting}>
                  Send Counterproposal
                </Button>
              </div>
            )}
            {app.proposed_amount && (
              <div className="mt-3 p-2 rounded-lg bg-[var(--color-warning)]/10 text-xs">
                <p className="font-medium text-[var(--color-warning)] mb-1">Active Counterproposal</p>
                <p className="text-[var(--color-text-muted)]">Amount: {formatCurrency(app.proposed_amount)}</p>
                <p className="text-[var(--color-text-muted)]">Rate: {app.proposed_rate}%</p>
                <p className="text-[var(--color-text-muted)]">Term: {app.proposed_term} months</p>
              </div>
            )}
          </Card>

          {/* Engine Suggestions Quick View */}
          {decision?.suggested_rate && (
            <Card padding="sm">
              <h3 className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider mb-2">Engine Suggestions</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Suggested Rate</span>
                  <span className="font-bold text-[var(--color-primary)]">{decision.suggested_rate}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Max Eligible</span>
                  <span className="font-bold text-[var(--color-primary)]">{formatCurrency(decision.suggested_amount)}</span>
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}


// ── Sub-Components ──────────────────────────────────

function InfoField({ label, value, highlight }: { label: string; value: any; highlight?: 'success' | 'danger' }) {
  const highlightColors = {
    success: 'text-[var(--color-success)]',
    danger: 'text-[var(--color-danger)]',
  };
  return (
    <div>
      <p className="text-xs text-[var(--color-text-muted)]">{label}</p>
      <p className={`font-medium text-sm ${highlight ? highlightColors[highlight] : 'text-[var(--color-text)]'} capitalize`}>
        {value != null && value !== '' ? String(value) : '-'}
      </p>
    </div>
  );
}

function EditableField({
  label, field, value, editing, editValues, setEditValues, type = 'text', prefix, suffix,
}: {
  label: string; field: string; value: any; editing: boolean;
  editValues: Record<string, any>; setEditValues: (v: Record<string, any>) => void;
  type?: string; prefix?: string; suffix?: string;
}) {
  if (!editing) {
    const display = value != null ? (prefix ? `${prefix} ${Number(value).toLocaleString()}` : suffix ? `${value} ${suffix}` : String(value)) : '-';
    return <InfoField label={label} value={display} />;
  }

  return (
    <div>
      <p className="text-xs text-[var(--color-text-muted)] mb-1">{label}</p>
      <div className="flex items-center space-x-1">
        {prefix && <span className="text-xs text-[var(--color-text-muted)]">{prefix}</span>}
        <input
          type={type}
          defaultValue={editValues[field] ?? value ?? ''}
          onChange={(e) => setEditValues({ ...editValues, [field]: type === 'number' ? parseFloat(e.target.value) : e.target.value })}
          className="w-full px-2 py-1 bg-[var(--color-bg)] border border-[var(--color-primary)]/50 rounded text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
        />
        {suffix && <span className="text-xs text-[var(--color-text-muted)]">{suffix}</span>}
      </div>
    </div>
  );
}

function BenchmarkBar({
  label, stated, benchMin, benchMax, flagged, matchFound, inverted,
}: {
  label: string; stated: number; benchMin: number; benchMax: number;
  flagged: boolean; matchFound: boolean; inverted?: boolean;
}) {
  const maxVal = Math.max(stated, benchMax) * 1.2;
  const statedPct = (stated / maxVal) * 100;
  const minPct = (benchMin / maxVal) * 100;
  const maxPct = (benchMax / maxVal) * 100;

  return (
    <div className="p-3 rounded-lg bg-[var(--color-bg)]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-[var(--color-text)]">{label}</span>
        {flagged ? (
          <Badge variant="danger">{inverted ? 'Understated' : 'Inflated'}</Badge>
        ) : (
          <Badge variant="success">Normal</Badge>
        )}
      </div>
      <div className="relative h-6 bg-[var(--color-surface)] rounded-full overflow-hidden mb-2">
        {/* Benchmark range */}
        <div
          className="absolute h-full bg-[var(--color-success)]/20 rounded-full"
          style={{ left: `${minPct}%`, width: `${maxPct - minPct}%` }}
        />
        {/* Stated value */}
        <div
          className="absolute h-full rounded-full"
          style={{
            width: `${statedPct}%`,
            backgroundColor: flagged ? 'var(--color-danger)' : 'var(--color-primary)',
            opacity: 0.6,
          }}
        />
      </div>
      <div className="flex justify-between text-xs text-[var(--color-text-muted)]">
        <span>Stated: <strong className="text-[var(--color-text)]">TTD {stated.toLocaleString()}</strong></span>
        <span>Benchmark: TTD {benchMin.toLocaleString()} - {benchMax.toLocaleString()}</span>
      </div>
      {!matchFound && (
        <p className="text-xs text-[var(--color-warning)] mt-1">Using default benchmark (no match for occupation)</p>
      )}
    </div>
  );
}


// ── Credit Bureau Tab ──────────────────────────────
function CreditBureauTab({ applicationId }: { applicationId: number }) {
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    underwriterApi.getCreditReport(applicationId)
      .then(res => setReport(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [applicationId]);

  const handleDownload = async () => {
    try {
      const res = await underwriterApi.downloadCreditReport(applicationId);
      const blob = new Blob([res.data], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `credit_report_${applicationId}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch { alert('Download failed'); }
  };

  if (loading) return <div className="text-[var(--color-text-muted)] py-8 text-center">Loading credit report...</div>;
  if (!report) return <Card><p className="text-[var(--color-text-muted)]">No credit report available. Run the decision engine first.</p></Card>;

  const data = report.report_data || {};
  const summary = data.summary || {};
  const insights = data.insights || [];
  const tradelines = data.tradelines || [];
  const inquiries = data.inquiries || [];
  const publicRecords = data.public_records || [];

  const riskColors: Record<string, string> = { Low: 'text-emerald-400', Medium: 'text-amber-400', High: 'text-orange-400', 'Very High': 'text-red-400' };

  return (
    <div className="space-y-4">
      {/* Summary */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-[var(--color-text)]">Credit Bureau Summary</h3>
          <Button size="sm" variant="outline" onClick={handleDownload}>Download Full Report</Button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-xs text-[var(--color-text-muted)]">Score</p>
            <p className="text-2xl font-bold text-[var(--color-text)]">{summary.score || report.score || '—'}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--color-text-muted)]">Risk Level</p>
            <p className={`text-lg font-bold ${riskColors[summary.risk_level || data.risk_level] || 'text-[var(--color-text)]'}`}>
              {summary.risk_level || data.risk_level || '—'}
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--color-text-muted)]">Total Debt</p>
            <p className="text-lg font-bold text-[var(--color-text)]">TTD {(summary.total_debt || data.total_outstanding_debt || 0).toLocaleString()}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--color-text-muted)]">Payment Rating</p>
            <p className="text-lg font-bold text-[var(--color-text)]">{summary.payment_history_rating || '—'}</p>
          </div>
        </div>
      </Card>

      {/* Insights */}
      {insights.length > 0 && (
        <Card>
          <h3 className="font-semibold text-[var(--color-text)] mb-3">Key Insights</h3>
          <ul className="space-y-1">
            {insights.map((insight: string, i: number) => (
              <li key={i} className="flex items-start space-x-2 text-sm">
                <span className="text-[var(--color-primary)] mt-0.5">•</span>
                <span className="text-[var(--color-text-muted)]">{insight}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* Tradelines */}
      {tradelines.length > 0 && (
        <Card padding="none">
          <div className="p-4 border-b border-[var(--color-border)]">
            <h3 className="font-semibold text-[var(--color-text)]">Tradelines ({tradelines.length})</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                  <th className="px-4 py-2 text-left">Lender</th>
                  <th className="px-4 py-2 text-left">Type</th>
                  <th className="px-4 py-2 text-left">Balance</th>
                  <th className="px-4 py-2 text-left">Monthly</th>
                  <th className="px-4 py-2 text-left">Status</th>
                  <th className="px-4 py-2 text-left">DPD</th>
                </tr>
              </thead>
              <tbody>
                {tradelines.map((t: any, i: number) => (
                  <tr key={i} className="border-b border-[var(--color-border)]">
                    <td className="px-4 py-2">{t.lender}</td>
                    <td className="px-4 py-2 text-[var(--color-text-muted)]">{t.type}</td>
                    <td className="px-4 py-2">TTD {(t.current_balance || 0).toLocaleString()}</td>
                    <td className="px-4 py-2">TTD {(t.monthly_payment || 0).toLocaleString()}</td>
                    <td className="px-4 py-2">
                      <Badge variant={t.status === 'current' ? 'success' : 'danger'}>{t.status}</Badge>
                    </td>
                    <td className="px-4 py-2">{t.days_past_due || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Inquiries */}
      {inquiries.length > 0 && (
        <Card padding="none">
          <div className="p-4 border-b border-[var(--color-border)]">
            <h3 className="font-semibold text-[var(--color-text)]">Inquiries ({inquiries.length})</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                  <th className="px-4 py-2 text-left">Lender</th>
                  <th className="px-4 py-2 text-left">Date</th>
                  <th className="px-4 py-2 text-left">Purpose</th>
                  <th className="px-4 py-2 text-left">Type</th>
                </tr>
              </thead>
              <tbody>
                {inquiries.map((inq: any, i: number) => (
                  <tr key={i} className="border-b border-[var(--color-border)]">
                    <td className="px-4 py-2">{inq.lender}</td>
                    <td className="px-4 py-2 text-[var(--color-text-muted)]">{inq.date}</td>
                    <td className="px-4 py-2">{inq.purpose}</td>
                    <td className="px-4 py-2">{inq.type || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Public Records */}
      {publicRecords.length > 0 && (
        <Card>
          <h3 className="font-semibold text-[var(--color-danger)] mb-3">Public Records ({publicRecords.length})</h3>
          {publicRecords.map((r: any, i: number) => (
            <div key={i} className="p-3 rounded-lg bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/30 mb-2">
              <div className="flex justify-between">
                <span className="font-medium text-[var(--color-danger)]">{r.type}</span>
                <Badge variant={r.status === 'active' ? 'danger' : 'success'}>{r.status}</Badge>
              </div>
              <p className="text-sm text-[var(--color-text-muted)] mt-1">
                Date: {r.date} | Amount: TTD {(r.amount || 0).toLocaleString()}
              </p>
              {r.court && <p className="text-xs text-[var(--color-text-muted)]">{r.court} - {r.case_number}</p>}
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}


// ── Payments Tab ────────────────────────────────────
function PaymentsTab({ applicationId }: { applicationId: number }) {
  const [payments, setPayments] = useState<any[]>([]);
  const [schedule, setSchedule] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ amount: '', payment_type: 'manual', payment_date: new Date().toISOString().split('T')[0], reference_number: '', notes: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadData();
  }, [applicationId]);

  const loadData = async () => {
    try {
      const [payRes, schedRes] = await Promise.all([
        paymentsApi.getHistory(applicationId),
        paymentsApi.getSchedule(applicationId),
      ]);
      setPayments(payRes.data);
      setSchedule(schedRes.data);
    } catch { /* ignore */ }
    setLoading(false);
  };

  const handleRecord = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await paymentsApi.recordPayment(applicationId, {
        amount: parseFloat(form.amount),
        payment_type: form.payment_type,
        payment_date: form.payment_date,
        reference_number: form.reference_number || undefined,
        notes: form.notes || undefined,
      });
      setShowForm(false);
      setForm({ amount: '', payment_type: 'manual', payment_date: new Date().toISOString().split('T')[0], reference_number: '', notes: '' });
      loadData();
    } catch { /* ignore */ }
    setSaving(false);
  };

  const inputClass = "w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]";
  const totalPaid = payments.reduce((s, p) => s + (p.amount || 0), 0);

  if (loading) return <div className="text-[var(--color-text-muted)] py-8 text-center">Loading payments...</div>;

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        <Card padding="sm">
          <p className="text-xs text-[var(--color-text-muted)]">Total Paid</p>
          <p className="text-lg font-bold text-[var(--color-success)]">TTD {totalPaid.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
        </Card>
        <Card padding="sm">
          <p className="text-xs text-[var(--color-text-muted)]">Payments</p>
          <p className="text-lg font-bold text-[var(--color-text)]">{payments.length}</p>
        </Card>
        <Card padding="sm">
          <p className="text-xs text-[var(--color-text-muted)]">Schedule Items</p>
          <p className="text-lg font-bold text-[var(--color-text)]">{schedule.length}</p>
        </Card>
      </div>

      {/* Record Payment Button */}
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowForm(!showForm)}>Record Payment</Button>
      </div>

      {showForm && (
        <Card>
          <h3 className="font-semibold mb-3">Record Payment</h3>
          <form onSubmit={handleRecord} className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Amount (TTD)</label>
              <input type="number" value={form.amount} onChange={e => setForm(f => ({ ...f, amount: e.target.value }))} className={inputClass} required step="0.01" />
            </div>
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Date</label>
              <input type="date" value={form.payment_date} onChange={e => setForm(f => ({ ...f, payment_date: e.target.value }))} className={inputClass} required />
            </div>
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Type</label>
              <select value={form.payment_type} onChange={e => setForm(f => ({ ...f, payment_type: e.target.value }))} className={inputClass}>
                <option value="manual">Manual</option>
                <option value="bank_transfer">Bank Transfer</option>
                <option value="online">Online</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Reference #</label>
              <input type="text" value={form.reference_number} onChange={e => setForm(f => ({ ...f, reference_number: e.target.value }))} className={inputClass} />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Notes</label>
              <input type="text" value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} className={inputClass} />
            </div>
            <div className="col-span-2 flex justify-end space-x-2">
              <Button variant="secondary" size="sm" type="button" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button size="sm" type="submit" isLoading={saving}>Save</Button>
            </div>
          </form>
        </Card>
      )}

      {/* Payment History */}
      {payments.length > 0 && (
        <Card padding="none">
          <div className="p-4 border-b border-[var(--color-border)]">
            <h3 className="font-semibold text-[var(--color-text)]">Payment History</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                  <th className="px-4 py-2 text-left">Date</th>
                  <th className="px-4 py-2 text-left">Amount</th>
                  <th className="px-4 py-2 text-left">Type</th>
                  <th className="px-4 py-2 text-left">Reference</th>
                  <th className="px-4 py-2 text-left">Status</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((p: any) => (
                  <tr key={p.id} className="border-b border-[var(--color-border)]">
                    <td className="px-4 py-2">{p.payment_date}</td>
                    <td className="px-4 py-2 font-medium text-[var(--color-success)]">TTD {p.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                    <td className="px-4 py-2 capitalize text-[var(--color-text-muted)]">{p.payment_type}</td>
                    <td className="px-4 py-2 font-mono text-xs">{p.reference_number || '—'}</td>
                    <td className="px-4 py-2"><Badge variant={p.status === 'completed' ? 'success' : 'warning'}>{p.status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Payment Schedule */}
      {schedule.length > 0 && (
        <Card padding="none">
          <div className="p-4 border-b border-[var(--color-border)]">
            <h3 className="font-semibold text-[var(--color-text)]">Payment Schedule</h3>
          </div>
          <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-[var(--color-surface)]">
                <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                  <th className="px-4 py-2 text-left">#</th>
                  <th className="px-4 py-2 text-left">Due Date</th>
                  <th className="px-4 py-2 text-right">Principal</th>
                  <th className="px-4 py-2 text-right">Interest</th>
                  <th className="px-4 py-2 text-right">Due</th>
                  <th className="px-4 py-2 text-right">Paid</th>
                  <th className="px-4 py-2 text-left">Status</th>
                </tr>
              </thead>
              <tbody>
                {schedule.map((s: any) => {
                  const statusVariant = s.status === 'paid' ? 'success' : s.status === 'overdue' ? 'danger' : s.status === 'partial' ? 'warning' : 'info';
                  return (
                    <tr key={s.id} className="border-b border-[var(--color-border)]">
                      <td className="px-4 py-2 text-[var(--color-text-muted)]">{s.installment_number}</td>
                      <td className="px-4 py-2">{s.due_date}</td>
                      <td className="px-4 py-2 text-right">{Number(s.principal).toFixed(2)}</td>
                      <td className="px-4 py-2 text-right text-[var(--color-text-muted)]">{Number(s.interest).toFixed(2)}</td>
                      <td className="px-4 py-2 text-right font-medium">{Number(s.amount_due).toFixed(2)}</td>
                      <td className="px-4 py-2 text-right text-[var(--color-success)]">{Number(s.amount_paid).toFixed(2)}</td>
                      <td className="px-4 py-2"><Badge variant={statusVariant}>{s.status}</Badge></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
