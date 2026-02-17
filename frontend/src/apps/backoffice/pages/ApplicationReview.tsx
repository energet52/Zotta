import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, Shield, AlertTriangle, CheckCircle, XCircle,
  FileText, Edit3, Save, X, Send, History, Calculator, Paperclip,
  Banknote, Download, Trash2, Calendar, DollarSign, MessageSquare, Plus
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import Badge, { getStatusBadge } from '../../../components/ui/Badge';
import ReferencesEditor from '../../../components/ReferencesEditor';
import type { Reference } from '../../../components/ReferencesEditor';
import { underwriterApi, loanApi, paymentsApi } from '../../../api/endpoints';
import SearchableSelect from '../../../components/ui/SearchableSelect';
import { OCCUPATION_OPTIONS } from '../../../constants/occupations';
import { Users } from 'lucide-react';

const EMPLOYER_SECTORS = [
  'Banking & Financial Services', 'Insurance', 'Hospitality & Tourism',
  'Agriculture & Agro-processing', 'Oil & Gas / Energy', 'Mining & Extractives',
  'Telecommunications', 'Retail & Distribution', 'Real Estate & Construction',
  'Manufacturing', 'Transportation & Logistics', 'Healthcare & Pharmaceuticals',
  'Education', 'Government & Public Sector', 'Utilities (Water & Electricity)',
  'Creative Industries & Entertainment', 'Maritime & Shipping',
  'Professional Services (Legal, Accounting, Consulting)',
  'Information Technology', 'Microfinance & Credit Unions', 'Other', 'Not Applicable',
];

// ── Types ───────────────────────────────────────
interface Profile {
  id: number;
  user_id: number;
  date_of_birth: string | null;
  id_type: string | null;
  national_id: string | null;
  gender: string | null;
  marital_status: string | null;
  address_line1: string | null;
  city: string | null;
  parish: string | null;
  whatsapp_number?: string | null;
  contact_email?: string | null;
  mobile_phone?: string | null;
  home_phone?: string | null;
  employer_phone?: string | null;
  employer_name: string | null;
  employer_sector: string | null;
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

type TabKey = 'details' | 'decision' | 'credit_bureau' | 'bank_analysis' | 'references' | 'documents' | 'schedule' | 'transactions' | 'audit';

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

  // Document upload (back-office)
  const [docUploadType, setDocUploadType] = useState('other');
  const [docUploadFile, setDocUploadFile] = useState<File | null>(null);
  const [docUploading, setDocUploading] = useState(false);
  const [docDeleting, setDocDeleting] = useState<number | null>(null);

  // Void
  const [showVoidDialog, setShowVoidDialog] = useState(false);
  const [voidReason, setVoidReason] = useState('');
  const [voiding, setVoiding] = useState(false);

  // Disbursement
  const [showDisburse, setShowDisburse] = useState(false);
  const [disbursing, setDisbursing] = useState(false);
  const [disbursementMethod, setDisbursementMethod] = useState('manual');
  const [disbursementNotes, setDisbursementNotes] = useState('');
  const [bankAccountName, setBankAccountName] = useState('');
  const [bankAccountNumber, setBankAccountNumber] = useState('');
  const [bankName, setBankName] = useState('');
  const [bankBranch, setBankBranch] = useState('');
  const [disbursementInfo, setDisbursementInfo] = useState<any>(null);
  const [schedule, setSchedule] = useState<any[]>([]);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [showRepaymentForm, setShowRepaymentForm] = useState(false);
  const [repaymentData, setRepaymentData] = useState({ amount: '', payment_type: 'manual', payment_date: new Date().toISOString().split('T')[0], reference_number: '', notes: '' });
  const [recordingPayment, setRecordingPayment] = useState(false);
  const [notes, setNotes] = useState<any[]>([]);
  const [newNote, setNewNote] = useState('');
  const [appComments, setAppComments] = useState<any[]>([]);
  const [newReply, setNewReply] = useState('');
  const [addingReply, setAddingReply] = useState(false);
  const [references, setReferences] = useState<Reference[]>([]);
  const [addingNote, setAddingNote] = useState(false);
  const [engineRunning, setEngineRunning] = useState(false);
  const engineAutoRanRef = React.useRef(false);

  // Compute a projected amortization schedule from application data
  const computeProjectedSchedule = (principal: number, annualRate: number, termMonths: number) => {
    if (!principal || !termMonths || principal <= 0 || termMonths <= 0) return [];
    const r = annualRate / 100 / 12;
    let pmt: number;
    if (r > 0) {
      pmt = principal * (r * Math.pow(1 + r, termMonths)) / (Math.pow(1 + r, termMonths) - 1);
    } else {
      pmt = principal / termMonths;
    }
    const rows: any[] = [];
    let balance = principal;
    const startDate = new Date();
    for (let i = 1; i <= termMonths; i++) {
      const interestPortion = balance * r;
      const principalPortion = pmt - interestPortion;
      balance = Math.max(0, balance - principalPortion);
      const dueDate = new Date(startDate);
      dueDate.setMonth(dueDate.getMonth() + i);
      rows.push({
        id: i,
        installment_number: i,
        due_date: dueDate.toISOString().split('T')[0],
        principal: Math.round(principalPortion * 100) / 100,
        interest: Math.round(interestPortion * 100) / 100,
        fee: 0,
        amount_due: Math.round(pmt * 100) / 100,
        amount_paid: 0,
        status: 'projected',
      });
    }
    return rows;
  };

  const loadData = () => {
    if (!id) return;
    setLoading(true);
    underwriterApi.getFullApplication(parseInt(id))
      .then((res) => {
        setData(res.data);
        const d = res.data.decisions?.[0];
        const req = res.data.application?.amount_requested;
        const amt = d?.suggested_amount != null && req != null
          ? Math.min(Number(req), Number(d.suggested_amount))
          : (d?.suggested_amount ?? req);
        if (amt != null) setApprovedAmount(String(amt));
        // Rate comes from credit product, not decision engine
        const productRate = res.data.application?.credit_product_rate;
        if (productRate != null) {
          setApprovedRate(String(productRate));
        } else if (d?.suggested_rate != null) {
          setApprovedRate(String(d.suggested_rate));
        }
        // Load disbursement info if disbursed
        if (res.data.application?.status === 'disbursed') {
          underwriterApi.getDisbursement(parseInt(id))
            .then((dRes) => setDisbursementInfo(dRes.data))
            .catch(() => setDisbursementInfo(null));
        }
        // Always try to load payment schedule and transactions
        setScheduleLoading(true);
        Promise.all([
          paymentsApi.getSchedule(parseInt(id)).catch(() => ({ data: [] })),
          paymentsApi.getHistory(parseInt(id)).catch(() => ({ data: [] })),
        ]).then(([sRes, tRes]) => {
          setSchedule(sRes.data || []);
          setTransactions(tRes.data || []);
        }).finally(() => setScheduleLoading(false));
        // Load notes
        underwriterApi.listNotes(parseInt(id))
          .then((nRes) => setNotes(nRes.data || []))
          .catch(() => setNotes([]));
        // Load applicant comments
        loanApi.listComments(parseInt(id))
          .then((cRes) => setAppComments(cRes.data || []))
          .catch(() => setAppComments([]));
        // Load references
        loanApi.listReferences(parseInt(id))
          .then((rRes) => setReferences(rRes.data || []))
          .catch(() => setReferences([]));

        // Auto-run decision engine if no decisions exist yet
        const hasDecisions = (res.data.decisions || []).length > 0;
        const appStatus = res.data.application?.status;
        const canAutoRun = !hasDecisions && !engineAutoRanRef.current
          && appStatus !== 'draft' && appStatus !== 'cancelled' && appStatus !== 'voided';
        if (canAutoRun) {
          engineAutoRanRef.current = true;
          setEngineRunning(true);
          underwriterApi.runEngine(parseInt(id))
            .then(() => {
              // Reload to pick up the new decision
              underwriterApi.getFullApplication(parseInt(id)).then((freshRes) => {
                setData(freshRes.data);
                const freshD = freshRes.data.decisions?.[0];
                const freshReq = freshRes.data.application?.amount_requested;
                const freshAmt = freshD?.suggested_amount != null && freshReq != null
                  ? Math.min(Number(freshReq), Number(freshD.suggested_amount))
                  : (freshD?.suggested_amount ?? freshReq);
                if (freshAmt != null) setApprovedAmount(String(freshAmt));
                const freshProductRate = freshRes.data.application?.credit_product_rate;
                if (freshProductRate != null) {
                  setApprovedRate(String(freshProductRate));
                } else if (freshD?.suggested_rate != null) {
                  setApprovedRate(String(freshD.suggested_rate));
                }
              }).catch(() => {});
            })
            .catch(() => {})
            .finally(() => setEngineRunning(false));
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { engineAutoRanRef.current = false; loadData(); }, [id]);

  const handleDecide = async () => {
    if (!action || !reason) { setError('Select action and provide a reason'); return; }
    setSubmitting(true); setError('');
    try {
      await underwriterApi.decide(parseInt(id!), { action, reason });
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

  const handleDisburse = async () => {
    setDisbursing(true); setError('');
    try {
      const payload: any = {
        method: disbursementMethod,
        notes: disbursementNotes || undefined,
      };
      if (disbursementMethod === 'bank_transfer') {
        payload.recipient_account_name = bankAccountName || undefined;
        payload.recipient_account_number = bankAccountNumber || undefined;
        payload.recipient_bank = bankName || undefined;
        payload.recipient_bank_branch = bankBranch || undefined;
      }
      const res = await underwriterApi.disburse(parseInt(id!), payload);
      setDisbursementInfo(res.data);
      setSuccessMsg(`Loan disbursed — ref ${res.data.reference_number}`);
      setShowDisburse(false);
      loadData();
    } catch (err: any) {
      setError(parseApiError(err, 'Disbursement failed'));
    } finally { setDisbursing(false); }
  };

  const handleVoid = async () => {
    if (!id || !voidReason.trim()) return;
    setVoiding(true); setError('');
    try {
      await underwriterApi.voidApplication(parseInt(id), voidReason.trim());
      setSuccessMsg('Application voided');
      setShowVoidDialog(false);
      setVoidReason('');
      loadData();
    } catch (err: any) {
      setError(parseApiError(err, 'Void failed'));
    } finally { setVoiding(false); }
  };

  const handleDocUpload = async () => {
    if (!id || !docUploadFile) return;
    setDocUploading(true); setError('');
    try {
      const formData = new FormData();
      formData.append('document_type', docUploadType);
      formData.append('file', docUploadFile);
      await underwriterApi.uploadDocument(parseInt(id), formData);
      setSuccessMsg('Document uploaded');
      setDocUploadFile(null);
      loadData();
    } catch (err: any) {
      setError(parseApiError(err, 'Upload failed'));
    } finally { setDocUploading(false); }
  };

  const handleDocDownload = async (docId: number, fileName: string) => {
    if (!id) return;
    try {
      const res = await underwriterApi.downloadDocument(parseInt(id), docId);
      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName || 'document';
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* ignore */ }
  };

  const handleDocDelete = async (docId: number) => {
    if (!id) return;
    setDocDeleting(docId);
    try {
      await underwriterApi.deleteDocument(parseInt(id), docId);
      setSuccessMsg('Document deleted');
      loadData();
    } catch (err: any) {
      setError(parseApiError(err, 'Delete failed'));
    } finally { setDocDeleting(null); }
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
    { key: 'decision', label: 'Credit Analysis', icon: Shield },
    { key: 'credit_bureau', label: 'Credit Bureau', icon: Shield },
    { key: 'bank_analysis', label: 'Bank Analysis', icon: Banknote },
    { key: 'references', label: 'References', icon: Users },
    { key: 'documents', label: 'Documents & Contract', icon: Paperclip },
    ...(app.status === 'disbursed' ? [
      { key: 'schedule' as TabKey, label: 'Payment Schedule', icon: Calendar },
      { key: 'transactions' as TabKey, label: 'Transactions', icon: DollarSign },
    ] : []),
    { key: 'audit', label: 'Audit History', icon: History },
  ];

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
                  <InfoField label="ID Type" value={profile?.id_type === 'drivers_license' ? "Driver's License" : profile?.id_type === 'passport' ? 'Passport' : profile?.id_type === 'tax_number' ? 'Tax Number' : profile?.id_type === 'national_id' ? 'National ID' : profile?.id_type} />
                  <InfoField label="ID Number" value={profile?.national_id} />
                  <InfoField label="Date of Birth" value={profile?.date_of_birth} />
                  <InfoField label="Gender" value={profile?.gender} />
                  <InfoField label="Marital Status" value={profile?.marital_status} />
                  <InfoField label="Address" value={profile?.address_line1} />
                  <InfoField label="City" value={profile?.city} />
                  <InfoField label="Parish" value={profile?.parish} />
                  <InfoField label="ID Verified" value={profile?.id_verified ? 'Yes' : 'No'} />
                </div>

                {/* Contact Details */}
                <h4 className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider mb-3">Contact Details</h4>
                <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 mb-6 text-sm">
                  <EditableField label="WhatsApp" field="whatsapp_number" value={profile?.whatsapp_number} editing={editing} editValues={editValues} setEditValues={setEditValues} />
                  <EditableField label="Contact Email" field="contact_email" value={profile?.contact_email} editing={editing} editValues={editValues} setEditValues={setEditValues} />
                  <EditableField label="Mobile Phone" field="mobile_phone" value={profile?.mobile_phone} editing={editing} editValues={editValues} setEditValues={setEditValues} />
                  <EditableField label="Home Phone" field="home_phone" value={profile?.home_phone} editing={editing} editValues={editValues} setEditValues={setEditValues} />
                  <EditableField label="Employer Phone" field="employer_phone" value={profile?.employer_phone} editing={editing} editValues={editValues} setEditValues={setEditValues} />
                </div>

                {/* Employment */}
                <h4 className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider mb-3">Employment & Financials</h4>
                <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 mb-6 text-sm">
                  <EditableField label="Employer" field="employer_name" value={profile?.employer_name} editing={editing} editValues={editValues} setEditValues={setEditValues} />
                  {editing ? (
                    <SearchableSelect
                      label="Employment Sector"
                      labelClassName="text-xs text-[var(--color-text-muted)] mb-1 block"
                      value={editValues.employer_sector ?? profile?.employer_sector ?? ''}
                      onChange={(v) => setEditValues({ ...editValues, employer_sector: v })}
                      options={EMPLOYER_SECTORS.map(s => ({ value: s, label: s }))}
                      placeholder="Search sector..."
                    />
                  ) : (
                    <InfoField label="Employment Sector" value={profile?.employer_sector || '-'} />
                  )}
                  {editing ? (
                    <SearchableSelect
                      label="Occupation / Job Title"
                      labelClassName="text-xs text-[var(--color-text-muted)] mb-1 block"
                      value={editValues.job_title ?? profile?.job_title ?? ''}
                      onChange={(v) => setEditValues({ ...editValues, job_title: v })}
                      options={OCCUPATION_OPTIONS.map(s => ({ value: s, label: s }))}
                      placeholder="Search occupation..."
                      allowOther
                      otherPlaceholder="Enter occupation..."
                    />
                  ) : (
                    <InfoField label="Occupation / Job Title" value={profile?.job_title || '-'} />
                  )}
                  <EditableField label="Employment Type" field="employment_type" value={profile?.employment_type} editing={editing} editValues={editValues} setEditValues={setEditValues} />
                  <EditableField label="Years Employed" field="years_employed" value={profile?.years_employed} editing={editing} editValues={editValues} setEditValues={setEditValues} type="number" />
                  <EditableField label="Monthly Income" field="monthly_income" value={profile?.monthly_income} editing={editing} editValues={editValues} setEditValues={setEditValues} type="number" prefix="TTD" />
                  <InfoField label="Other Income" value={profile?.other_income != null ? formatCurrency(profile.other_income) : '-'} />
                  <EditableField label="Monthly Expenses" field="monthly_expenses" value={profile?.monthly_expenses} editing={editing} editValues={editValues} setEditValues={setEditValues} type="number" prefix="TTD" />
                  <EditableField label="Existing Debt" field="existing_debt" value={profile?.existing_debt} editing={editing} editValues={editValues} setEditValues={setEditValues} type="number" prefix="TTD" />
                  <InfoField label="Dependents" value={profile?.dependents} />
                </div>

                {/* Loan Details — Shopping + Plan Selection (same as consumer portal) */}
                <h4 className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider mb-3">Loan Details</h4>
                <div className="space-y-4">
                  {/* Shopping Context */}
                  {(app.merchant_name || app.branch_name || (app.items && app.items.length > 0)) && (
                    <div className="p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
                      <h5 className="text-xs font-medium text-[var(--color-text-muted)] uppercase mb-2">Shopping Context</h5>
                      <div className="grid grid-cols-2 gap-2 text-sm mb-3">
                        <InfoField label="Merchant" value={app.merchant_name || '—'} />
                        <InfoField label="Branch" value={app.branch_name || '—'} />
                      </div>
                      {app.items && app.items.length > 0 && (
                        <>
                          <h5 className="text-xs font-medium text-[var(--color-text-muted)] uppercase mb-2">Items</h5>
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="text-left text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                                  <th className="py-2 pr-2">Category</th>
                                  <th className="py-2 pr-2">Price</th>
                                  <th className="py-2 pr-2">Qty</th>
                                  <th className="py-2 pr-2">Description</th>
                                  <th className="py-2">Total</th>
                                </tr>
                              </thead>
                              <tbody>
                                {app.items.map((it: any) => (
                                  <tr key={it.id} className="border-b border-[var(--color-border)]/50">
                                    <td className="py-2 pr-2">{it.category_name || '—'}</td>
                                    <td className="py-2 pr-2">{formatCurrency(it.price)}</td>
                                    <td className="py-2 pr-2">{it.quantity}</td>
                                    <td className="py-2 pr-2">{it.description || '—'}</td>
                                    <td className="py-2 font-medium">{formatCurrency((it.price || 0) * (it.quantity || 1))}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          <p className="text-sm mt-2">
                            <span className="text-[var(--color-text-muted)]">Total Purchase:</span>{' '}
                            <span className="font-bold text-[var(--color-text)]">
                              {formatCurrency(app.items.reduce((s: number, it: any) => s + (it.price || 0) * (it.quantity || 1), 0))}
                            </span>
                          </p>
                        </>
                      )}
                    </div>
                  )}
                  {/* Plan Selection */}
                  <div className="p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
                    <h5 className="text-xs font-medium text-[var(--color-text-muted)] uppercase mb-2">Plan Selection</h5>
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
                      <InfoField label="Credit Product" value={app.credit_product_name || '—'} />
                      <EditableField label="Term" field="term_months" value={app.term_months} editing={editing} editValues={editValues} setEditValues={setEditValues} type="number" suffix="months" />
                      <InfoField label="Total Financed" value={formatCurrency(app.total_financed)} />
                      <InfoField label="Downpayment" value={formatCurrency(app.downpayment)} />
                      <InfoField label="Monthly Payment" value={formatCurrency(app.monthly_payment)} />
                    </div>
                  </div>
                  {/* Standard fields */}
                  <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 text-sm">
                    <InfoField label="Amount Requested" value={formatCurrency(app.amount_requested)} />
                    <InfoField label="Submitted" value={app.submitted_at ? new Date(app.submitted_at).toLocaleString() : '-'} />
                    {app.amount_approved && <InfoField label="Amount Approved" value={formatCurrency(app.amount_approved)} highlight="success" />}
                    {app.interest_rate && <InfoField label="Interest Rate" value={`${app.interest_rate}%`} />}
                  </div>
                  {data.contract?.signed_at && (
                    <div className="flex items-center justify-between pt-2 mt-2 border-t border-[var(--color-border)]">
                      <span className="text-[var(--color-text-muted)]">Hire Purchase Agreement and Consent</span>
                      <span className="text-xs text-[var(--color-success)]">Signed</span>
                    </div>
                  )}
                </div>
              </Card>

              {/* Payment Schedule – shown inline for non-disbursed applications with known amounts */}
              {app.status !== 'disbursed' && (() => {
                const loanAmt = Number(app.amount_approved || app.amount_requested || 0);
                const rate = Number(app.interest_rate || 0);
                const term = Number(app.term_months || 0);
                // Use actual schedule (disbursed) or compute projected
                const displaySchedule = schedule.length > 0 ? schedule : computeProjectedSchedule(loanAmt, rate, term);
                const isProjected = schedule.length === 0 && displaySchedule.length > 0;
                if (scheduleLoading || displaySchedule.length === 0) {
                  return loanAmt > 0 && term > 0 ? (
                    <Card>
                      <h3 className="font-semibold text-[var(--color-text)] mb-4 flex items-center">
                        <Calendar size={18} className="mr-2 text-[var(--color-primary)]" />
                        Payment Schedule
                      </h3>
                      <p className="text-sm text-[var(--color-text-muted)]">{scheduleLoading ? 'Loading schedule...' : 'Interest rate not yet determined. Schedule will appear once the application is approved.'}</p>
                    </Card>
                  ) : null;
                }
                return (
                  <Card>
                    <h3 className="font-semibold text-[var(--color-text)] mb-4 flex items-center">
                      <Calendar size={18} className="mr-2 text-[var(--color-primary)]" />
                      Payment Schedule
                      {isProjected && <Badge variant="warning" className="ml-2 text-[10px]">Projected</Badge>}
                    </h3>
                    {/* Summary totals */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                      <div className="p-3 rounded-lg bg-[var(--color-bg)]">
                        <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Loan Amount</p>
                        <p className="text-lg font-bold text-[var(--color-text)]">{formatCurrency(loanAmt)}</p>
                      </div>
                      <div className="p-3 rounded-lg bg-[var(--color-bg)]">
                        <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Total Interest</p>
                        <p className="text-lg font-bold text-[var(--color-text)]">{formatCurrency(displaySchedule.reduce((s: number, r: any) => s + Number(r.interest || 0), 0))}</p>
                      </div>
                      <div className="p-3 rounded-lg bg-[var(--color-bg)]">
                        <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Total Fees</p>
                        <p className="text-lg font-bold text-[var(--color-text)]">{formatCurrency(displaySchedule.reduce((s: number, r: any) => s + Number(r.fee || 0), 0))}</p>
                      </div>
                      <div className="p-3 rounded-lg bg-[var(--color-bg)]">
                        <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Total Payable</p>
                        <p className="text-lg font-bold text-[var(--color-primary)]">{formatCurrency(displaySchedule.reduce((s: number, r: any) => s + Number(r.amount_due || 0), 0))}</p>
                      </div>
                    </div>
                    {/* Schedule table */}
                    <div className="overflow-x-auto max-h-72 overflow-y-auto border border-[var(--color-border)] rounded-lg">
                      <table className="min-w-full text-xs">
                        <thead className="bg-[var(--color-bg)] sticky top-0">
                          <tr>
                            <th className="px-3 py-2 text-left text-[var(--color-text-muted)]">#</th>
                            <th className="px-3 py-2 text-left text-[var(--color-text-muted)]">Due Date</th>
                            <th className="px-3 py-2 text-right text-[var(--color-text-muted)]">Principal</th>
                            <th className="px-3 py-2 text-right text-[var(--color-text-muted)]">Interest</th>
                            <th className="px-3 py-2 text-right text-[var(--color-text-muted)]">Amount Due</th>
                            {!isProjected && <th className="px-3 py-2 text-right text-[var(--color-text-muted)]">Paid</th>}
                            <th className="px-3 py-2 text-center text-[var(--color-text-muted)]">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--color-border)]">
                          {displaySchedule.map((row: any) => (
                            <tr key={row.id} className="hover:bg-[var(--color-bg)]/50">
                              <td className="px-3 py-2 text-[var(--color-text)]">{row.installment_number}</td>
                              <td className="px-3 py-2 text-[var(--color-text)]">{row.due_date ? new Date(row.due_date).toLocaleDateString() : '-'}</td>
                              <td className="px-3 py-2 text-right text-[var(--color-text)]">{formatCurrency(row.principal)}</td>
                              <td className="px-3 py-2 text-right text-[var(--color-text)]">{formatCurrency(row.interest)}</td>
                              <td className="px-3 py-2 text-right font-medium text-[var(--color-text)]">{formatCurrency(row.amount_due)}</td>
                              {!isProjected && <td className="px-3 py-2 text-right text-[var(--color-text)]">{formatCurrency(row.amount_paid)}</td>}
                              <td className="px-3 py-2 text-center">
                                <Badge variant={row.status === 'paid' ? 'success' : row.status === 'overdue' ? 'danger' : row.status === 'projected' ? 'info' : 'warning'}>
                                  {row.status}
                                </Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {isProjected && (
                      <p className="text-xs text-[var(--color-text-muted)] mt-2 italic">
                        This is a projected schedule based on the current loan terms. Actual schedule will be generated upon disbursement.
                      </p>
                    )}
                  </Card>
                );
              })()}
            </div>
          )}

          {/* Tab: Credit Analysis */}
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
                      {Object.entries(decision.scoring_breakdown).filter(([, v]) => typeof v === 'number' && v <= 100).map(([key, value]) => (
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

              {/* Re-run analysis */}
              <div className="flex items-center justify-between pt-2">
                <p className="text-xs text-[var(--color-text-muted)]">
                  Analysis run on {decision.created_at ? new Date(decision.created_at).toLocaleString() : 'unknown date'}
                </p>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={async () => {
                    setSubmitting(true); setError('');
                    try {
                      await underwriterApi.runEngine(parseInt(id!));
                      setSuccessMsg('Analysis refreshed');
                      loadData();
                    } catch (err: any) {
                      setError(parseApiError(err, 'Failed to re-run analysis'));
                    } finally { setSubmitting(false); }
                  }}
                  isLoading={submitting}
                >
                  <Calculator size={14} className="mr-1" />
                  Re-run Analysis
                </Button>
              </div>
            </div>
          )}

          {activeTab === 'decision' && !decision && (
            <Card>
              <div className="text-center py-8">
                {engineRunning ? (
                  <>
                    <div className="animate-spin rounded-full h-8 w-8 border-2 border-[var(--color-primary)] border-t-transparent mx-auto mb-3" />
                    <p className="text-[var(--color-text-muted)]">Running credit analysis...</p>
                    <p className="text-xs text-[var(--color-text-muted)] mt-1">This usually takes a few seconds</p>
                  </>
                ) : (
                  <>
                    <Shield size={32} className="mx-auto text-[var(--color-text-muted)] mb-3" />
                    <p className="text-[var(--color-text-muted)] mb-1">Decision analysis could not be completed automatically.</p>
                    <p className="text-xs text-[var(--color-text-muted)] mb-4">This may happen if required data (credit bureau, profile) was not available at submission time.</p>
                    <Button
                      onClick={async () => {
                        setSubmitting(true); setError('');
                        try {
                          await underwriterApi.runEngine(parseInt(id!));
                          setSuccessMsg('Decision analysis completed');
                          loadData();
                        } catch (err: any) {
                          setError(parseApiError(err, 'Failed to run decision analysis'));
                        } finally { setSubmitting(false); }
                      }}
                      isLoading={submitting}
                    >
                      <Calculator size={16} className="mr-2" />
                      Retry Analysis
                    </Button>
                  </>
                )}
              </div>
            </Card>
          )}

          {/* Tab: References */}
          {activeTab === 'references' && (
            <Card>
              <ReferencesEditor
                references={references}
                onAdd={async (ref) => {
                  const res = await loanApi.addReference(parseInt(id!), ref);
                  setReferences((prev) => [...prev, res.data]);
                }}
                onUpdate={async (refId, ref) => {
                  const res = await loanApi.updateReference(parseInt(id!), refId, ref);
                  setReferences((prev) => prev.map((r) => r.id === refId ? res.data : r));
                }}
                onDelete={async (refId) => {
                  await loanApi.deleteReference(parseInt(id!), refId);
                  setReferences((prev) => prev.filter((r) => r.id !== refId));
                }}
              />
            </Card>
          )}

          {/* Tab: Documents & Contract */}
          {activeTab === 'documents' && (
            <div className="space-y-4">
              <Card>
                <h3 className="font-semibold text-[var(--color-text)] mb-4">Upload Document</h3>
                <div className="flex flex-wrap gap-3 items-end mb-4 p-3 rounded-lg bg-[var(--color-bg)]">
                  <div>
                    <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Document Type</label>
                    <select
                      value={docUploadType}
                      onChange={(e) => setDocUploadType(e.target.value)}
                      className="px-3 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                    >
                      <option value="national_id">National ID</option>
                      <option value="passport">Passport</option>
                      <option value="drivers_license">Driver&apos;s License</option>
                      <option value="proof_of_income">Proof of Income</option>
                      <option value="bank_statement">Bank Statement</option>
                      <option value="utility_bill">Utility Bill</option>
                      <option value="employment_letter">Employment Letter</option>
                      <option value="other">Other</option>
                    </select>
                  </div>
                  <div className="flex-1 min-w-[180px]">
                    <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">File</label>
                    <input
                      type="file"
                      onChange={(e) => setDocUploadFile(e.target.files?.[0] || null)}
                      className="block w-full text-sm text-[var(--color-text-muted)] file:mr-2 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-[var(--color-primary)] file:text-white file:cursor-pointer"
                    />
                  </div>
                  <Button size="sm" onClick={handleDocUpload} isLoading={docUploading} disabled={!docUploadFile}>
                    <Paperclip size={14} className="mr-1" /> Upload
                  </Button>
                </div>

                <h3 className="font-semibold text-[var(--color-text)] mt-6 mb-4">Uploaded Documents</h3>
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
                        <div className="flex items-center gap-2">
                          {getStatusBadge(doc.status)}
                          <Button size="sm" variant="ghost" onClick={() => handleDocDownload(doc.id, doc.file_name)}>
                            <Download size={14} />
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => handleDocDelete(doc.id)} isLoading={docDeleting === doc.id}>
                            <Trash2 size={14} className="text-[var(--color-danger)]" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-[var(--color-text-muted)]">No documents uploaded</p>
                )}
              </Card>

              {/* Contract */}
              <Card>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold text-[var(--color-text)]">Contract</h3>
                  <div className="flex gap-2">
                    {data.contract?.signed_at && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={async () => {
                          try {
                            const res = await loanApi.getConsentPdf(parseInt(id!));
                            const blob = res.data instanceof Blob ? res.data : new Blob([res.data], { type: 'application/pdf' });
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `hire-purchase-agreement-signed-${app.reference_number}.pdf`;
                            a.click();
                            URL.revokeObjectURL(url);
                          } catch { /* ignore */ }
                        }}
                      >
                        <Download size={14} className="mr-1" /> Download Signed Contract (PDF)
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant={data.contract?.signed_at ? 'ghost' : 'outline'}
                      onClick={async () => {
                        try {
                          const res = await underwriterApi.generateContract(parseInt(id!));
                          const blob = new Blob([res.data], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url;
                          a.download = `contract-${app.reference_number}.docx`;
                          a.click();
                          URL.revokeObjectURL(url);
                        } catch { /* ignore */ }
                      }}
                    >
                      <FileText size={14} className="mr-1" /> {data.contract?.signed_at ? 'Download Contract (Word)' : 'Generate Contract for Printing'}
                    </Button>
                  </div>
                </div>
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
                  <div className="space-y-3">
                    <div className="flex items-center gap-3 p-4 bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30 rounded-lg">
                      <AlertTriangle size={18} className="text-[var(--color-warning)] shrink-0" />
                      <div>
                        <p className="text-sm font-medium text-[var(--color-text)]">Contract not yet signed</p>
                        <p className="text-xs text-[var(--color-text-muted)]">Use the &quot;Generate Contract for Printing&quot; button above to create a pre-filled contract PDF that can be printed and signed at the branch.</p>
                      </div>
                    </div>
                  </div>
                )}
              </Card>
            </div>
          )}

          {/* Tab: Payment Schedule (disbursed) */}
          {activeTab === 'schedule' && (
            <Card>
              <h3 className="font-semibold text-[var(--color-text)] mb-4 flex items-center">
                <Calendar size={18} className="mr-2 text-[var(--color-primary)]" />
                Payment Schedule
              </h3>
              {scheduleLoading ? (
                <p className="text-sm text-[var(--color-text-muted)]">Loading schedule...</p>
              ) : schedule.length > 0 ? (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                    <div className="p-3 rounded-lg bg-[var(--color-bg)]">
                      <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Loan Amount</p>
                      <p className="text-lg font-bold text-[var(--color-text)]">{formatCurrency(app.amount_approved || app.amount_requested)}</p>
                    </div>
                    <div className="p-3 rounded-lg bg-[var(--color-bg)]">
                      <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Total Interest</p>
                      <p className="text-lg font-bold text-[var(--color-text)]">{formatCurrency(schedule.reduce((s: number, r: any) => s + Number(r.interest || 0), 0))}</p>
                    </div>
                    <div className="p-3 rounded-lg bg-[var(--color-bg)]">
                      <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Total Fees</p>
                      <p className="text-lg font-bold text-[var(--color-text)]">{formatCurrency(schedule.reduce((s: number, r: any) => s + Number(r.fee || 0), 0))}</p>
                    </div>
                    <div className="p-3 rounded-lg bg-[var(--color-bg)]">
                      <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Total Payable</p>
                      <p className="text-lg font-bold text-[var(--color-primary)]">{formatCurrency(schedule.reduce((s: number, r: any) => s + Number(r.amount_due || 0), 0))}</p>
                    </div>
                  </div>
                  <div className="overflow-x-auto max-h-96 overflow-y-auto border border-[var(--color-border)] rounded-lg">
                    <table className="min-w-full text-xs">
                      <thead className="bg-[var(--color-bg)] sticky top-0">
                        <tr>
                          <th className="px-3 py-2 text-left text-[var(--color-text-muted)]">#</th>
                          <th className="px-3 py-2 text-left text-[var(--color-text-muted)]">Due Date</th>
                          <th className="px-3 py-2 text-right text-[var(--color-text-muted)]">Principal</th>
                          <th className="px-3 py-2 text-right text-[var(--color-text-muted)]">Interest</th>
                          <th className="px-3 py-2 text-right text-[var(--color-text-muted)]">Amount Due</th>
                          <th className="px-3 py-2 text-right text-[var(--color-text-muted)]">Paid</th>
                          <th className="px-3 py-2 text-center text-[var(--color-text-muted)]">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--color-border)]">
                        {schedule.map((row: any) => (
                          <tr key={row.id} className="hover:bg-[var(--color-bg)]/50">
                            <td className="px-3 py-2 text-[var(--color-text)]">{row.installment_number}</td>
                            <td className="px-3 py-2 text-[var(--color-text)]">{row.due_date ? new Date(row.due_date).toLocaleDateString() : '-'}</td>
                            <td className="px-3 py-2 text-right text-[var(--color-text)]">{formatCurrency(row.principal)}</td>
                            <td className="px-3 py-2 text-right text-[var(--color-text)]">{formatCurrency(row.interest)}</td>
                            <td className="px-3 py-2 text-right font-medium text-[var(--color-text)]">{formatCurrency(row.amount_due)}</td>
                            <td className="px-3 py-2 text-right text-[var(--color-text)]">{formatCurrency(row.amount_paid)}</td>
                            <td className="px-3 py-2 text-center">
                              <Badge variant={row.status === 'paid' ? 'success' : row.status === 'overdue' ? 'danger' : 'warning'}>
                                {row.status}
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <p className="text-sm text-[var(--color-text-muted)]">No payment schedule available.</p>
              )}
            </Card>
          )}

          {/* Tab: Transactions (disbursed) */}
          {activeTab === 'transactions' && (
            <div className="space-y-4">
              <Card>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold text-[var(--color-text)] flex items-center">
                    <DollarSign size={18} className="mr-2 text-[var(--color-primary)]" />
                    Payment Transactions
                  </h3>
                  <Button size="sm" variant={showRepaymentForm ? 'ghost' : 'primary'} onClick={() => setShowRepaymentForm(!showRepaymentForm)}>
                    {showRepaymentForm ? <><X size={14} className="mr-1" /> Cancel</> : <><Plus size={14} className="mr-1" /> Register Repayment</>}
                  </Button>
                </div>

                {/* Register Repayment Form */}
                {showRepaymentForm && (
                  <div className="mb-4 p-4 rounded-lg border border-[var(--color-primary)]/30 bg-[var(--color-primary)]/5">
                    <h4 className="text-sm font-semibold text-[var(--color-text)] mb-3">Register Manual Repayment</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Amount *</label>
                        <input
                          type="number"
                          step="0.01"
                          min="0.01"
                          className="w-full px-3 py-2 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/40"
                          placeholder="0.00"
                          value={repaymentData.amount}
                          onChange={(e) => setRepaymentData(prev => ({ ...prev, amount: e.target.value }))}
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Payment Type</label>
                        <select
                          className="w-full px-3 py-2 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/40"
                          value={repaymentData.payment_type}
                          onChange={(e) => setRepaymentData(prev => ({ ...prev, payment_type: e.target.value }))}
                        >
                          <option value="manual">Manual / Cash</option>
                          <option value="bank_transfer">Bank Transfer</option>
                          <option value="online">Online Payment</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Payment Date *</label>
                        <input
                          type="date"
                          className="w-full px-3 py-2 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/40"
                          value={repaymentData.payment_date}
                          onChange={(e) => setRepaymentData(prev => ({ ...prev, payment_date: e.target.value }))}
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Reference Number</label>
                        <input
                          type="text"
                          className="w-full px-3 py-2 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/40"
                          placeholder="e.g. receipt or transfer ref"
                          value={repaymentData.reference_number}
                          onChange={(e) => setRepaymentData(prev => ({ ...prev, reference_number: e.target.value }))}
                        />
                      </div>
                      <div className="md:col-span-2">
                        <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Notes</label>
                        <input
                          type="text"
                          className="w-full px-3 py-2 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/40"
                          placeholder="Optional notes about this payment"
                          value={repaymentData.notes}
                          onChange={(e) => setRepaymentData(prev => ({ ...prev, notes: e.target.value }))}
                        />
                      </div>
                    </div>
                    <div className="flex justify-end mt-3 gap-2">
                      <Button size="sm" variant="ghost" onClick={() => setShowRepaymentForm(false)}>Cancel</Button>
                      <Button
                        size="sm"
                        variant="primary"
                        disabled={recordingPayment || !repaymentData.amount || Number(repaymentData.amount) <= 0 || !repaymentData.payment_date}
                        onClick={async () => {
                          setRecordingPayment(true);
                          try {
                            await paymentsApi.recordPayment(parseInt(id!), {
                              amount: Number(repaymentData.amount),
                              payment_type: repaymentData.payment_type,
                              payment_date: repaymentData.payment_date,
                              reference_number: repaymentData.reference_number || undefined,
                              notes: repaymentData.notes || undefined,
                            });
                            // Refresh transactions and schedule
                            const [tRes, sRes] = await Promise.all([
                              paymentsApi.getHistory(parseInt(id!)).catch(() => ({ data: [] })),
                              paymentsApi.getSchedule(parseInt(id!)).catch(() => ({ data: [] })),
                            ]);
                            setTransactions(tRes.data || []);
                            setSchedule(sRes.data || []);
                            setRepaymentData({ amount: '', payment_type: 'manual', payment_date: new Date().toISOString().split('T')[0], reference_number: '', notes: '' });
                            setShowRepaymentForm(false);
                          } catch { /* ignore */ }
                          setRecordingPayment(false);
                        }}
                      >
                        {recordingPayment ? 'Recording...' : <><Banknote size={14} className="mr-1" /> Record Payment</>}
                      </Button>
                    </div>
                  </div>
                )}

                {/* Transactions Table */}
                {transactions.length > 0 ? (
                  <div className="overflow-x-auto max-h-96 overflow-y-auto border border-[var(--color-border)] rounded-lg">
                    <table className="min-w-full text-xs">
                      <thead className="bg-[var(--color-bg)] sticky top-0">
                        <tr>
                          <th className="px-3 py-2 text-left text-[var(--color-text-muted)]">Date</th>
                          <th className="px-3 py-2 text-right text-[var(--color-text-muted)]">Amount</th>
                          <th className="px-3 py-2 text-left text-[var(--color-text-muted)]">Type</th>
                          <th className="px-3 py-2 text-left text-[var(--color-text-muted)]">Reference</th>
                          <th className="px-3 py-2 text-center text-[var(--color-text-muted)]">Status</th>
                          <th className="px-3 py-2 text-left text-[var(--color-text-muted)]">Notes</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--color-border)]">
                        {transactions.map((t: any) => (
                          <tr key={t.id} className="hover:bg-[var(--color-bg)]/50">
                            <td className="px-3 py-2 text-[var(--color-text)]">{t.payment_date ? new Date(t.payment_date).toLocaleDateString() : '-'}</td>
                            <td className="px-3 py-2 text-right font-medium text-[var(--color-text)]">{formatCurrency(t.amount)}</td>
                            <td className="px-3 py-2 text-[var(--color-text)] capitalize">{(t.payment_type || '').replace(/_/g, ' ')}</td>
                            <td className="px-3 py-2 font-mono text-[var(--color-text-muted)]">{t.reference_number || '—'}</td>
                            <td className="px-3 py-2 text-center">
                              <Badge variant={t.status === 'completed' ? 'success' : t.status === 'failed' ? 'danger' : 'warning'}>
                                {t.status}
                              </Badge>
                            </td>
                            <td className="px-3 py-2 text-[var(--color-text-muted)] max-w-[150px] truncate">{t.notes || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-[var(--color-text-muted)]">No payment transactions recorded yet.</p>
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
                      document_uploaded: 'var(--color-primary)',
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

          {activeTab === 'bank_analysis' && (
            <BankStatementAnalysisTab
              applicationId={parseInt(id!)}
              documents={data.documents}
            />
          )}
        </div>

        {/* Right Sidebar - Decision Panel */}
        <div className="space-y-4">
          <Card>
            <h3 className="font-semibold text-[var(--color-text)] mb-4">Underwriter Decision</h3>

            {error && <div className="mb-3 p-2 rounded-lg bg-[var(--color-danger)]/15 text-[var(--color-danger)] text-xs">{error}</div>}

            {['approved', 'accepted', 'offer_sent', 'disbursed'].includes(app.status) ? (
              <div className="space-y-3">
                <div className={`p-3 rounded-lg border text-sm ${
                  app.status === 'disbursed'
                    ? 'bg-blue-500/10 border-blue-500/20'
                    : 'bg-[var(--color-success)]/10 border-[var(--color-success)]/20'
                }`}>
                  <div className="flex items-center space-x-2 mb-1">
                    <span className={`w-2 h-2 rounded-full ${
                      app.status === 'disbursed' ? 'bg-blue-500' : 'bg-[var(--color-success)]'
                    }`} />
                    <span className={`text-xs font-semibold ${
                      app.status === 'disbursed' ? 'text-blue-400' : 'text-[var(--color-success)]'
                    }`}>
                      {app.status === 'disbursed' ? 'Loan Disbursed' : 'Decision Final'}
                    </span>
                  </div>
                  <p className="text-xs text-[var(--color-text-muted)]">
                    {app.status === 'disbursed'
                      ? 'This loan has been disbursed. The decision and status can no longer be changed.'
                      : 'This application has been approved. The decision can no longer be changed.'}
                  </p>
                  {app.amount_approved && (
                    <div className="mt-2 pt-2 border-t border-[var(--color-border)] flex gap-4 text-xs">
                      <div>
                        <span className="text-[var(--color-text-muted)]">Amount:</span>{' '}
                        <span className="font-semibold text-[var(--color-text)]">{formatCurrency(app.amount_approved)}</span>
                      </div>
                      {app.interest_rate && (
                        <div>
                          <span className="text-[var(--color-text-muted)]">Rate:</span>{' '}
                          <span className="font-semibold text-[var(--color-text)]">{app.interest_rate}%</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ) : (
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
                <div className="space-y-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] p-3 text-sm">
                  <p className="text-[var(--color-text-muted)]">Approved Amount & Rate (from credit product — not editable)</p>
                  <div className="flex gap-4">
                    <div>
                      <span className="text-[var(--color-text-muted)]">Amount:</span>{' '}
                      <span className="font-semibold text-[var(--color-text)]">
                        {approvedAmount ? `TTD ${parseFloat(approvedAmount).toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '—'}
                      </span>
                    </div>
                    <div>
                      <span className="text-[var(--color-text-muted)]">Rate:</span>{' '}
                      <span className="font-semibold text-[var(--color-text)]">
                        {approvedRate ? `${approvedRate}%` : '—'}
                      </span>
                    </div>
                  </div>
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
            )}
          </Card>

          {/* Counterproposal — only when decision hasn't been finalized */}
          {!['approved', 'accepted', 'offer_sent', 'disbursed'].includes(app.status) && (
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
          )}

          {/* Disbursement Panel */}
          {['approved', 'accepted', 'offer_sent'].includes(app.status) && (
            <Card>
              <div className="flex items-center space-x-2 mb-3">
                <div className="p-1.5 rounded-lg bg-[var(--color-success)]/15">
                  <Banknote size={18} className="text-[var(--color-success)]" />
                </div>
                <h3 className="font-semibold text-[var(--color-text)]">Disburse Loan</h3>
              </div>
              <p className="text-xs text-[var(--color-text-muted)] mb-3">
                Release funds to the applicant. This will transition the loan to
                "Disbursed" and generate the payment schedule.
              </p>
              <div className="mb-3 p-2 rounded-lg bg-[var(--color-primary)]/10 text-xs space-y-1">
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Approved Amount</span>
                  <span className="font-bold text-[var(--color-text)]">{formatCurrency(app.amount_approved)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Interest Rate</span>
                  <span className="font-bold text-[var(--color-text)]">{app.interest_rate ? `${app.interest_rate}%` : '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Term</span>
                  <span className="font-bold text-[var(--color-text)]">{app.term_months} months</span>
                </div>
              </div>

              {!showDisburse ? (
                <Button className="w-full" variant="success" onClick={() => setShowDisburse(true)} disabled={!app.amount_approved}>
                  <Banknote size={14} className="mr-1" /> Disburse Funds
                </Button>
              ) : (
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Disbursement Method</label>
                    <select
                      value={disbursementMethod}
                      onChange={(e) => setDisbursementMethod(e.target.value)}
                      className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                    >
                      <option value="manual">Manual (Cash / Cheque)</option>
                      <option value="bank_transfer">Bank Transfer</option>
                      <option value="cheque">Cheque</option>
                    </select>
                  </div>

                  {disbursementMethod === 'bank_transfer' && (
                    <div className="space-y-2 p-2 rounded-lg border border-[var(--color-border)]">
                      <p className="text-xs font-medium text-[var(--color-text-muted)]">Recipient Bank Details</p>
                      <input
                        type="text" placeholder="Account Name"
                        value={bankAccountName} onChange={(e) => setBankAccountName(e.target.value)}
                        className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                      />
                      <input
                        type="text" placeholder="Account Number"
                        value={bankAccountNumber} onChange={(e) => setBankAccountNumber(e.target.value)}
                        className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                      />
                      <input
                        type="text" placeholder="Bank Name"
                        value={bankName} onChange={(e) => setBankName(e.target.value)}
                        className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                      />
                      <input
                        type="text" placeholder="Branch (optional)"
                        value={bankBranch} onChange={(e) => setBankBranch(e.target.value)}
                        className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                      />
                    </div>
                  )}

                  <div>
                    <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Notes (optional)</label>
                    <textarea
                      value={disbursementNotes}
                      onChange={(e) => setDisbursementNotes(e.target.value)}
                      rows={2}
                      className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                      placeholder="Disbursement notes..."
                    />
                  </div>

                  <div className="flex space-x-2">
                    <Button className="flex-1" variant="success" onClick={handleDisburse} isLoading={disbursing}>
                      <CheckCircle size={14} className="mr-1" /> Confirm Disbursement
                    </Button>
                    <Button variant="ghost" onClick={() => setShowDisburse(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </Card>
          )}

          {/* Disbursement Details (when already disbursed) */}
          {app.status === 'disbursed' && disbursementInfo && (
            <Card>
              <div className="flex items-center space-x-2 mb-3">
                <div className="p-1.5 rounded-lg bg-[var(--color-success)]/15">
                  <CheckCircle size={18} className="text-[var(--color-success)]" />
                </div>
                <h3 className="font-semibold text-[var(--color-text)]">Disbursement Details</h3>
              </div>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Reference</span>
                  <span className="font-mono font-medium text-[var(--color-text)]">{disbursementInfo.reference_number}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Amount</span>
                  <span className="font-bold text-[var(--color-success)]">{formatCurrency(disbursementInfo.amount)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Method</span>
                  <span className="text-[var(--color-text)] capitalize">{disbursementInfo.method?.replace('_', ' ')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Status</span>
                  <span className={`font-medium capitalize ${
                    disbursementInfo.status === 'completed' ? 'text-[var(--color-success)]' :
                    disbursementInfo.status === 'failed' ? 'text-[var(--color-danger)]' :
                    'text-[var(--color-warning)]'
                  }`}>{disbursementInfo.status}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Disbursed By</span>
                  <span className="text-[var(--color-text)]">{disbursementInfo.disbursed_by_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Disbursed At</span>
                  <span className="text-[var(--color-text)]">{new Date(disbursementInfo.disbursed_at).toLocaleString()}</span>
                </div>
                {disbursementInfo.recipient_bank && (
                  <div className="mt-2 p-2 rounded-lg bg-[var(--color-surface-hover)] space-y-1">
                    <p className="font-medium text-[var(--color-text-muted)]">Bank Details</p>
                    <p className="text-[var(--color-text)]">{disbursementInfo.recipient_account_name}</p>
                    <p className="text-[var(--color-text)]">{disbursementInfo.recipient_bank} — {disbursementInfo.recipient_account_number}</p>
                    {disbursementInfo.recipient_bank_branch && <p className="text-[var(--color-text-muted)]">{disbursementInfo.recipient_bank_branch}</p>}
                  </div>
                )}
                {disbursementInfo.notes && (
                  <div className="mt-1 p-2 rounded-lg bg-[var(--color-bg)] text-[var(--color-text-muted)] italic">
                    {disbursementInfo.notes}
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* Void Application */}
          {!['disbursed', 'cancelled', 'voided'].includes(app.status) && (
            <Card className="border-red-200/50">
              <div className="flex items-center space-x-2 mb-2">
                <div className="p-1.5 rounded-lg bg-red-500/15">
                  <XCircle size={18} className="text-red-500" />
                </div>
                <h3 className="font-semibold text-[var(--color-text)]">Void Application</h3>
              </div>
              <p className="text-xs text-[var(--color-text-muted)] mb-3">
                Permanently void this application. This cannot be undone.
              </p>
              {!showVoidDialog ? (
                <Button
                  size="sm"
                  className="w-full !bg-red-600 hover:!bg-red-700 text-white"
                  onClick={() => setShowVoidDialog(true)}
                >
                  <XCircle size={14} className="mr-1" /> Void Application
                </Button>
              ) : (
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">
                      Reason <span className="text-red-500">*</span>
                    </label>
                    <textarea
                      value={voidReason}
                      onChange={e => setVoidReason(e.target.value)}
                      rows={3}
                      className="w-full px-3 py-2 bg-[var(--color-bg)] border border-red-300 rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-red-400 resize-none"
                      placeholder="Reason for voiding (required)..."
                    />
                  </div>
                  <div className="flex space-x-2">
                    <Button
                      size="sm"
                      className="flex-1 !bg-red-600 hover:!bg-red-700 text-white"
                      onClick={handleVoid}
                      isLoading={voiding}
                      disabled={!voidReason.trim()}
                    >
                      Confirm Void
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => { setShowVoidDialog(false); setVoidReason(''); }}>
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </Card>
          )}

          {/* Voided Banner */}
          {app.status === 'voided' && (
            <Card className="border-red-200 bg-red-50">
              <div className="flex items-center space-x-2 mb-2">
                <XCircle size={18} className="text-red-600" />
                <h3 className="font-semibold text-red-800">Application Voided</h3>
              </div>
              <p className="text-sm text-red-700">
                This application has been voided and cannot be processed further.
              </p>
            </Card>
          )}

          {/* Cancelled Banner */}
          {app.status === 'cancelled' && (
            <Card className="border-orange-200 bg-orange-50">
              <div className="flex items-center space-x-2 mb-2">
                <XCircle size={18} className="text-orange-600" />
                <h3 className="font-semibold text-orange-800">Application Cancelled</h3>
              </div>
              <p className="text-sm text-orange-700">
                This application was cancelled by the applicant.
              </p>
            </Card>
          )}

          {/* Notes */}
          <Card>
            <h3 className="font-semibold text-[var(--color-text)] mb-3 flex items-center">
              <MessageSquare size={16} className="mr-2 text-[var(--color-primary)]" />
              Notes
              {notes.length > 0 && <span className="ml-auto text-xs text-[var(--color-text-muted)]">{notes.length}</span>}
            </h3>
            <div className="space-y-2 mb-3">
              <textarea
                value={newNote}
                onChange={(e) => setNewNote(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] resize-none"
                placeholder="Add a note..."
              />
              <Button
                size="sm"
                className="w-full"
                disabled={!newNote.trim() || addingNote}
                isLoading={addingNote}
                onClick={async () => {
                  if (!newNote.trim()) return;
                  setAddingNote(true);
                  try {
                    const res = await underwriterApi.addNote(parseInt(id!), newNote.trim());
                    setNotes((prev) => [res.data, ...prev]);
                    setNewNote('');
                  } catch { /* ignore */ }
                  setAddingNote(false);
                }}
              >
                <Plus size={14} className="mr-1" /> Add Note
              </Button>
            </div>
            {notes.length > 0 && (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {notes.map((n: any) => (
                  <div key={n.id} className="p-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
                    <p className="text-sm text-[var(--color-text)] whitespace-pre-wrap">{n.content}</p>
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-[10px] text-[var(--color-text-muted)]">{n.user_name}</span>
                      <span className="text-[10px] text-[var(--color-text-muted)]">{n.created_at ? new Date(n.created_at).toLocaleString() : ''}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Applicant Messages */}
          <Card>
            <h3 className="font-semibold text-[var(--color-text)] mb-3 flex items-center">
              <MessageSquare size={16} className="mr-2 text-[var(--color-info,var(--color-primary))]" />
              Applicant Messages
              {appComments.length > 0 && <span className="ml-auto text-xs bg-[var(--color-primary)] text-white rounded-full px-1.5 py-0.5">{appComments.filter((c: any) => c.is_from_applicant).length}</span>}
            </h3>

            {/* Messages thread */}
            <div className="space-y-2 max-h-64 overflow-y-auto mb-3 border border-[var(--color-border)] rounded-lg p-2 bg-[var(--color-bg)]">
              {appComments.length === 0 ? (
                <p className="text-xs text-[var(--color-text-muted)] text-center py-3">No messages from applicant</p>
              ) : (
                appComments.map((c: any) => (
                  <div
                    key={c.id}
                    className={`flex ${c.is_from_applicant ? 'justify-start' : 'justify-end'}`}
                  >
                    <div className={`max-w-[85%] rounded-lg px-2.5 py-1.5 text-xs ${
                      c.is_from_applicant
                        ? 'bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text)] rounded-bl-none'
                        : 'bg-[var(--color-primary)] text-white rounded-br-none'
                    }`}>
                      <p className={`text-[10px] font-semibold mb-0.5 ${c.is_from_applicant ? 'text-[var(--color-text-muted)]' : 'text-white/70'}`}>
                        {c.is_from_applicant ? `${c.author_name} (Applicant)` : `${c.author_name} (Staff)`}
                      </p>
                      <p className="whitespace-pre-wrap">{c.content}</p>
                      <p className={`text-[9px] mt-0.5 ${c.is_from_applicant ? 'text-[var(--color-text-muted)]' : 'text-white/60'}`}>
                        {c.created_at ? new Date(c.created_at).toLocaleString() : ''}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Reply input */}
            <div className="space-y-2">
              <textarea
                value={newReply}
                onChange={(e) => setNewReply(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] resize-none"
                placeholder="Reply to applicant..."
              />
              <Button
                size="sm"
                className="w-full"
                disabled={!newReply.trim() || addingReply}
                isLoading={addingReply}
                onClick={async () => {
                  if (!newReply.trim()) return;
                  setAddingReply(true);
                  try {
                    const res = await loanApi.addComment(parseInt(id!), newReply.trim());
                    setAppComments((prev) => [...prev, res.data]);
                    setNewReply('');
                  } catch { /* ignore */ }
                  setAddingReply(false);
                }}
              >
                <Send size={14} className="mr-1" /> Send Reply
              </Button>
            </div>
          </Card>
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
  const subjectInfo = data.subject_info || {};
  const openContracts: any[] = data.open_contracts || [];
  const closedContracts: any[] = data.closed_contracts || [];
  const scoreHistory: any[] = data.score_history || [];
  const inquiriesDetail: any[] = data.inquiries_detail || data.inquiries || [];
  const inquiryCounts = data.inquiry_counts || {};
  const publicRecords: any[] = data.public_records || [];
  const insights: string[] = data.insights || [];

  const score = data.score || report.score || 0;
  const riskGrade = data.risk_grade || data.summary?.risk_grade || '—';
  const riskDesc = data.risk_description || data.summary?.risk_description || '—';
  const pd = data.probability_of_default ?? data.summary?.probability_of_default ?? null;
  const contractsSummary = data.contracts_summary || {};

  // Risk grade colour
  const gradeColor = (g: string) => {
    if (g.startsWith('A')) return 'text-emerald-400';
    if (g.startsWith('B')) return 'text-cyan-400';
    if (g.startsWith('C')) return 'text-amber-400';
    if (g.startsWith('D')) return 'text-orange-400';
    if (g.startsWith('E')) return 'text-red-400';
    return 'text-[var(--color-text)]';
  };

  const fmt = (v: number | null | undefined) =>
    v != null ? `TTD ${v.toLocaleString(undefined, { minimumFractionDigits: 0 })}` : '—';

  const SectionTitle = ({ children }: { children: React.ReactNode }) => (
    <h3 className="font-semibold text-[var(--color-text)] text-base">{children}</h3>
  );

  const InfoRow = ({ label, value }: { label: string; value: React.ReactNode }) => (
    <div className="flex justify-between py-1.5 border-b border-[var(--color-border)]/40 last:border-0">
      <span className="text-xs text-[var(--color-text-muted)]">{label}</span>
      <span className="text-sm text-[var(--color-text)] text-right">{value || '—'}</span>
    </div>
  );

  return (
    <div className="space-y-4">

      {/* ── Dashboard: Score + Risk Grade + Inquiries ── */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <SectionTitle>EveryData Credit Report</SectionTitle>
          <div className="flex items-center gap-2">
            {report.pulled_at && (
              <span className="text-xs text-[var(--color-text-muted)]">
                Pulled: {new Date(report.pulled_at).toLocaleDateString()}
              </span>
            )}
            <Button size="sm" variant="outline" onClick={handleDownload}>Download</Button>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {/* Score */}
          <div className="text-center p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
            <p className="text-xs text-[var(--color-text-muted)] mb-1">EveryData Score</p>
            <p className="text-3xl font-bold text-[var(--color-text)]">{score}</p>
          </div>
          {/* Risk Grade */}
          <div className="text-center p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
            <p className="text-xs text-[var(--color-text-muted)] mb-1">Risk Grade</p>
            <p className={`text-3xl font-bold ${gradeColor(riskGrade)}`}>{riskGrade}</p>
            <p className="text-[10px] text-[var(--color-text-muted)]">{riskDesc}</p>
          </div>
          {/* PD */}
          <div className="text-center p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
            <p className="text-xs text-[var(--color-text-muted)] mb-1">Probability of Default</p>
            <p className="text-2xl font-bold text-[var(--color-text)]">{pd != null ? `${pd}%` : '—'}</p>
          </div>
          {/* Inquiries 12m */}
          <div className="text-center p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
            <p className="text-xs text-[var(--color-text-muted)] mb-1">Inquiries (12 mo)</p>
            <p className="text-2xl font-bold text-[var(--color-text)]">{inquiryCounts['12_months'] ?? inquiriesDetail.length}</p>
          </div>
          {/* Active Contracts */}
          <div className="text-center p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
            <p className="text-xs text-[var(--color-text-muted)] mb-1">Open Contracts</p>
            <p className="text-2xl font-bold text-[var(--color-text)]">{contractsSummary.open_count ?? openContracts.length}</p>
          </div>
        </div>
      </Card>

      {/* ── Subject / Personal Info from Bureau ── */}
      {Object.keys(subjectInfo).length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Address & Contacts */}
          <Card>
            <SectionTitle>Bureau Contact Details</SectionTitle>
            <div className="mt-3">
              <InfoRow label="Full Name" value={subjectInfo.full_name} />
              <InfoRow label="Contact Address" value={subjectInfo.contact_address} />
              <InfoRow label="Mobile" value={subjectInfo.mobile} />
              <InfoRow label="Fixed Line" value={subjectInfo.fixed_line} />
              <InfoRow label="Email" value={subjectInfo.email} />
            </div>
          </Card>
          {/* Personal Data */}
          <Card>
            <SectionTitle>Bureau Personal Data</SectionTitle>
            <div className="mt-3">
              <InfoRow label="Date of Birth" value={subjectInfo.date_of_birth} />
              <InfoRow label="Tax Number" value={subjectInfo.tax_number_masked} />
              <InfoRow label="Gender" value={subjectInfo.gender} />
              <InfoRow label="Marital Status" value={subjectInfo.marital_status} />
              <InfoRow label="Citizenship" value={subjectInfo.citizenship} />
              <InfoRow label="Employment" value={subjectInfo.employment} />
              <InfoRow label="Education" value={subjectInfo.education} />
            </div>
          </Card>
        </div>
      )}

      {/* ── Open Contracts ── */}
      <Card padding="none">
        <div className="p-4 border-b border-[var(--color-border)] flex items-center justify-between">
          <SectionTitle>Open Contracts ({openContracts.length})</SectionTitle>
          {contractsSummary.total_amount != null && (
            <span className="text-xs text-[var(--color-text-muted)]">
              Total: {fmt(contractsSummary.total_amount)} &middot; Balance: {fmt(contractsSummary.total_balance)} &middot; Monthly: {fmt(contractsSummary.total_monthly_payments)}
            </span>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] text-xs">
                <th className="px-4 py-2 text-left">Sector</th>
                <th className="px-4 py-2 text-left">Type</th>
                <th className="px-4 py-2 text-left">Creditor</th>
                <th className="px-4 py-2 text-left">Opened</th>
                <th className="px-4 py-2 text-left">Updated</th>
                <th className="px-4 py-2 text-right">Total</th>
                <th className="px-4 py-2 text-right">Balance</th>
                <th className="px-4 py-2 text-right">Past Due</th>
                <th className="px-4 py-2 text-left">Arrears</th>
                <th className="px-4 py-2 text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {openContracts.length === 0 ? (
                <tr><td colSpan={10} className="px-4 py-4 text-center text-[var(--color-text-muted)]">No Data</td></tr>
              ) : openContracts.map((c: any, i: number) => (
                <tr key={i} className="border-b border-[var(--color-border)]">
                  <td className="px-4 py-2 text-[var(--color-text-muted)]">{c.sector}</td>
                  <td className="px-4 py-2">{c.type}</td>
                  <td className="px-4 py-2">{c.creditor}</td>
                  <td className="px-4 py-2 text-[var(--color-text-muted)] whitespace-nowrap">{c.opened_date}</td>
                  <td className="px-4 py-2 text-[var(--color-text-muted)] whitespace-nowrap">{c.last_updated}</td>
                  <td className="px-4 py-2 text-right whitespace-nowrap">{fmt(c.total_amount)}</td>
                  <td className="px-4 py-2 text-right whitespace-nowrap">{fmt(c.balance)}</td>
                  <td className="px-4 py-2 text-right whitespace-nowrap">{fmt(c.past_due)}</td>
                  <td className="px-4 py-2">{c.arrears_days} Days</td>
                  <td className="px-4 py-2">
                    <Badge variant={c.status === 'Granted And Activated' ? 'success' : c.status === 'Delinquent' ? 'danger' : 'default'}>
                      {c.status}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ── Closed Contracts ── */}
      <Card padding="none">
        <div className="p-4 border-b border-[var(--color-border)]">
          <SectionTitle>Closed Contracts ({closedContracts.length})</SectionTitle>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] text-xs">
                <th className="px-4 py-2 text-left">Sector</th>
                <th className="px-4 py-2 text-left">Type</th>
                <th className="px-4 py-2 text-left">Creditor</th>
                <th className="px-4 py-2 text-left">Opened</th>
                <th className="px-4 py-2 text-left">Closed</th>
                <th className="px-4 py-2 text-right">Total</th>
                <th className="px-4 py-2 text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {closedContracts.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-4 text-center text-[var(--color-text-muted)]">No Data</td></tr>
              ) : closedContracts.map((c: any, i: number) => (
                <tr key={i} className="border-b border-[var(--color-border)]">
                  <td className="px-4 py-2 text-[var(--color-text-muted)]">{c.sector}</td>
                  <td className="px-4 py-2">{c.type}</td>
                  <td className="px-4 py-2">{c.creditor}</td>
                  <td className="px-4 py-2 text-[var(--color-text-muted)] whitespace-nowrap">{c.opened_date}</td>
                  <td className="px-4 py-2 text-[var(--color-text-muted)] whitespace-nowrap">{c.real_end_date || '—'}</td>
                  <td className="px-4 py-2 text-right whitespace-nowrap">{fmt(c.total_amount)}</td>
                  <td className="px-4 py-2"><Badge variant="default">Closed</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ── Score History ── */}
      {scoreHistory.length > 0 && (
        <Card padding="none">
          <div className="p-4 border-b border-[var(--color-border)]">
            <SectionTitle>Score History</SectionTitle>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] text-xs">
                  {scoreHistory.map((h: any, i: number) => (
                    <th key={i} className="px-3 py-2 text-center whitespace-nowrap">{h.month}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-[var(--color-border)]">
                  {scoreHistory.map((h: any, i: number) => (
                    <td key={i} className="px-3 py-2 text-center font-bold text-[var(--color-text)]">{h.score}</td>
                  ))}
                </tr>
                <tr className="border-b border-[var(--color-border)]">
                  {scoreHistory.map((h: any, i: number) => (
                    <td key={i} className={`px-3 py-2 text-center text-xs font-semibold ${gradeColor(h.risk_grade)}`}>{h.risk_grade}</td>
                  ))}
                </tr>
                <tr>
                  {scoreHistory.map((h: any, i: number) => (
                    <td key={i} className="px-3 py-2 text-center text-xs text-[var(--color-text-muted)]">{h.probability_of_default}%</td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* ── Inquiries ── */}
      <Card padding="none">
        <div className="p-4 border-b border-[var(--color-border)] flex items-center justify-between">
          <SectionTitle>Inquiries</SectionTitle>
          {Object.keys(inquiryCounts).length > 0 && (
            <div className="flex gap-3 text-xs text-[var(--color-text-muted)]">
              <span>1m: <b className="text-[var(--color-text)]">{inquiryCounts['1_month'] ?? 0}</b></span>
              <span>3m: <b className="text-[var(--color-text)]">{inquiryCounts['3_months'] ?? 0}</b></span>
              <span>6m: <b className="text-[var(--color-text)]">{inquiryCounts['6_months'] ?? 0}</b></span>
              <span>12m: <b className="text-[var(--color-text)]">{inquiryCounts['12_months'] ?? 0}</b></span>
              <span>24m: <b className="text-[var(--color-text)]">{inquiryCounts['24_months'] ?? 0}</b></span>
            </div>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] text-xs">
                <th className="px-4 py-2 text-left">Date</th>
                <th className="px-4 py-2 text-left">Reason</th>
                <th className="px-4 py-2 text-left">Sector</th>
              </tr>
            </thead>
            <tbody>
              {inquiriesDetail.length === 0 ? (
                <tr><td colSpan={3} className="px-4 py-4 text-center text-[var(--color-text-muted)]">No Data</td></tr>
              ) : inquiriesDetail.map((inq: any, i: number) => (
                <tr key={i} className="border-b border-[var(--color-border)]">
                  <td className="px-4 py-2 whitespace-nowrap">{inq.date}</td>
                  <td className="px-4 py-2">{inq.reason || inq.purpose || '—'}</td>
                  <td className="px-4 py-2">{inq.sector || inq.lender || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ── Key Insights ── */}
      {insights.length > 0 && (
        <Card>
          <SectionTitle>Key Insights</SectionTitle>
          <ul className="mt-3 space-y-1">
            {insights.map((insight: string, i: number) => (
              <li key={i} className="flex items-start space-x-2 text-sm">
                <span className="text-[var(--color-primary)] mt-0.5">•</span>
                <span className="text-[var(--color-text-muted)]">{insight}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* ── Public Records ── */}
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


// ── Bank Statement Analysis Tab ───────────────────────

interface BankAnalysisData {
  id: number;
  loan_application_id: number;
  document_id: number;
  status: string;
  summary: string | null;
  cashflow_data: { inflows?: Record<string, number>; outflows?: Record<string, number> } | null;
  flags: { type: string; severity: string; detail: string; amount_involved?: number | null; occurrences?: number | null }[];
  volatility_score: number | null;
  monthly_stats: { month: string; total_inflow: number; total_outflow: number; net: number; min_balance?: number | null }[];
  risk_assessment: string | null;
  income_stability: string | null;
  avg_monthly_inflow: number | null;
  avg_monthly_outflow: number | null;
  avg_monthly_net: number | null;
  error_message: string | null;
  created_at: string;
}

function BankStatementAnalysisTab({
  applicationId,
  documents,
}: {
  applicationId: number;
  documents: DocumentInfo[];
}) {
  const [analysis, setAnalysis] = useState<BankAnalysisData | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState('');
  const [expandedMonth, setExpandedMonth] = useState<string | null>(null);

  const hasBankStatement = documents.some(d => d.document_type === 'bank_statement');

  useEffect(() => {
    underwriterApi.getBankAnalysis(applicationId)
      .then(res => setAnalysis(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [applicationId]);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setError('');
    try {
      const res = await underwriterApi.analyzeBankStatement(applicationId);
      setAnalysis(res.data);
    } catch (err: any) {
      setError(parseApiError(err, 'Analysis failed. Please try again.'));
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading) return <div className="text-[var(--color-text-muted)] py-8 text-center">Loading bank analysis...</div>;

  // No analysis yet — show trigger
  if (!analysis) {
    return (
      <Card>
        <div className="text-center py-8">
          <Banknote size={48} className="mx-auto text-[var(--color-text-muted)] mb-4" />
          <h3 className="text-lg font-semibold text-[var(--color-text)] mb-2">Bank Statement Analysis</h3>
          <p className="text-sm text-[var(--color-text-muted)] mb-6 max-w-md mx-auto">
            Use AI to analyze uploaded bank statements. The system will categorize transactions,
            detect income volatility, and flag concerning patterns such as gambling or cash-squeeze behaviour.
          </p>
          {!hasBankStatement ? (
            <p className="text-sm text-[var(--color-warning)]">
              No bank statement uploaded yet. Please upload one in the Documents tab first.
            </p>
          ) : (
            <Button onClick={handleAnalyze} isLoading={analyzing}>
              <Banknote size={16} className="mr-2" />
              Analyze Bank Statement
            </Button>
          )}
          {error && <p className="text-sm text-[var(--color-danger)] mt-4">{error}</p>}
        </div>
      </Card>
    );
  }

  // Analysis failed
  if (analysis.status === 'failed') {
    return (
      <Card>
        <div className="text-center py-8">
          <AlertTriangle size={48} className="mx-auto text-[var(--color-danger)] mb-4" />
          <h3 className="text-lg font-semibold text-[var(--color-danger)] mb-2">Analysis Failed</h3>
          <p className="text-sm text-[var(--color-text-muted)] mb-4">{analysis.error_message || 'An unknown error occurred.'}</p>
          {hasBankStatement && (
            <Button onClick={handleAnalyze} isLoading={analyzing} variant="secondary">
              Retry Analysis
            </Button>
          )}
        </div>
      </Card>
    );
  }

  // Helpers
  const fmt = (v: number | null | undefined) => {
    if (v == null) return '-';
    return `TTD ${Number(v).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  };

  const riskColors: Record<string, string> = {
    low: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    moderate: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
    high: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
    very_high: 'bg-red-200 text-red-900 dark:bg-red-900/50 dark:text-red-300',
  };

  const severityColors: Record<string, string> = {
    low: 'border-yellow-300 bg-yellow-50 dark:bg-yellow-950/20 dark:border-yellow-800',
    medium: 'border-orange-300 bg-orange-50 dark:bg-orange-950/20 dark:border-orange-800',
    high: 'border-red-400 bg-red-50 dark:bg-red-950/20 dark:border-red-800',
  };

  const severityIcons: Record<string, string> = {
    low: 'text-yellow-500',
    medium: 'text-orange-500',
    high: 'text-red-500',
  };

  const flagLabels: Record<string, string> = {
    gambling: 'Gambling / Betting',
    cash_squeeze: 'Cash Squeeze',
    high_cash_withdrawals: 'High Cash Withdrawals',
    irregular_income: 'Irregular Income',
    bounce_nsf: 'Bounced Payments / NSF',
    high_debt_service: 'High Debt Service',
    declining_balance: 'Declining Balance',
    unexplained_large_transactions: 'Large Unexplained Transactions',
  };

  const volatilityColor = (score: number) => {
    if (score <= 25) return 'bg-green-500';
    if (score <= 50) return 'bg-yellow-500';
    if (score <= 75) return 'bg-orange-500';
    return 'bg-red-500';
  };

  return (
    <div className="space-y-4">
      {/* Summary Card */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-[var(--color-primary)]/10 flex items-center justify-center">
              <Banknote size={20} className="text-[var(--color-primary)]" />
            </div>
            <div>
              <h3 className="font-semibold text-[var(--color-text)]">Bank Statement Analysis</h3>
              <p className="text-xs text-[var(--color-text-muted)]">
                Analyzed on {new Date(analysis.created_at).toLocaleDateString()} at {new Date(analysis.created_at).toLocaleTimeString()}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            {analysis.risk_assessment && (
              <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase ${riskColors[analysis.risk_assessment] || riskColors.moderate}`}>
                {analysis.risk_assessment.replace('_', ' ')} Risk
              </span>
            )}
            {hasBankStatement && (
              <button
                onClick={handleAnalyze}
                disabled={analyzing}
                className="text-xs text-[var(--color-primary)] hover:underline disabled:opacity-50"
              >
                {analyzing ? 'Re-analyzing...' : 'Re-analyze'}
              </button>
            )}
          </div>
        </div>

        {/* Narrative Summary */}
        {analysis.summary && (
          <div className="p-4 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] mb-4">
            <p className="text-sm text-[var(--color-text)] leading-relaxed">{analysis.summary}</p>
          </div>
        )}

        {/* Key Metrics Row */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <div className="text-center p-3 rounded-lg bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800">
            <p className="text-[10px] uppercase font-bold text-green-600 dark:text-green-400 tracking-wider">Avg Monthly In</p>
            <p className="text-lg font-bold text-green-600 dark:text-green-400">{fmt(analysis.avg_monthly_inflow)}</p>
          </div>
          <div className="text-center p-3 rounded-lg bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800">
            <p className="text-[10px] uppercase font-bold text-red-600 dark:text-red-400 tracking-wider">Avg Monthly Out</p>
            <p className="text-lg font-bold text-red-600 dark:text-red-400">{fmt(analysis.avg_monthly_outflow)}</p>
          </div>
          <div className={`text-center p-3 rounded-lg border ${(analysis.avg_monthly_net ?? 0) >= 0 ? 'bg-green-50 dark:bg-green-950/20 border-green-200 dark:border-green-800' : 'bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-800'}`}>
            <p className="text-[10px] uppercase font-bold text-[var(--color-text-muted)] tracking-wider">Avg Net</p>
            <p className={`text-lg font-bold ${(analysis.avg_monthly_net ?? 0) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>{fmt(analysis.avg_monthly_net)}</p>
          </div>
          <div className="text-center p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
            <p className="text-[10px] uppercase font-bold text-[var(--color-text-muted)] tracking-wider">Income Stability</p>
            <p className="text-sm font-bold text-[var(--color-text)] capitalize mt-1">{analysis.income_stability || '-'}</p>
          </div>
          <div className="text-center p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
            <p className="text-[10px] uppercase font-bold text-[var(--color-text-muted)] tracking-wider mb-1">Volatility</p>
            <div className="flex items-center justify-center space-x-2">
              <div className="flex-1 h-2 rounded-full bg-[var(--color-border)] overflow-hidden max-w-[80px]">
                <div
                  className={`h-full rounded-full ${volatilityColor(analysis.volatility_score ?? 0)}`}
                  style={{ width: `${analysis.volatility_score ?? 0}%` }}
                />
              </div>
              <span className="text-sm font-bold text-[var(--color-text)]">{Math.round(analysis.volatility_score ?? 0)}</span>
            </div>
          </div>
        </div>
      </Card>

      {/* Flags */}
      {analysis.flags && analysis.flags.length > 0 && (
        <Card>
          <h3 className="font-semibold text-[var(--color-text)] mb-3 flex items-center">
            <AlertTriangle size={18} className="mr-2 text-[var(--color-warning)]" />
            Flagged Concerns ({analysis.flags.length})
          </h3>
          <div className="space-y-2">
            {analysis.flags
              .sort((a, b) => {
                const order: Record<string, number> = { high: 0, medium: 1, low: 2 };
                return (order[a.severity] ?? 2) - (order[b.severity] ?? 2);
              })
              .map((flag, i) => (
              <div
                key={i}
                className={`p-3 rounded-lg border ${severityColors[flag.severity] || severityColors.low}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-2">
                    <AlertTriangle size={16} className={severityIcons[flag.severity] || 'text-yellow-500'} />
                    <span className="font-medium text-sm text-[var(--color-text)]">
                      {flagLabels[flag.type] || flag.type.replace(/_/g, ' ')}
                    </span>
                    <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded ${
                      flag.severity === 'high' ? 'bg-red-200 text-red-800 dark:bg-red-800 dark:text-red-200'
                      : flag.severity === 'medium' ? 'bg-orange-200 text-orange-800 dark:bg-orange-800 dark:text-orange-200'
                      : 'bg-yellow-200 text-yellow-800 dark:bg-yellow-800 dark:text-yellow-200'
                    }`}>
                      {flag.severity}
                    </span>
                  </div>
                  <div className="flex items-center space-x-3 text-xs text-[var(--color-text-muted)]">
                    {flag.amount_involved != null && <span>{fmt(flag.amount_involved)}</span>}
                    {flag.occurrences != null && <span>{flag.occurrences}x</span>}
                  </div>
                </div>
                <p className="text-sm text-[var(--color-text-muted)] mt-1 ml-6">{flag.detail}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Monthly Cashflow Table */}
      {analysis.monthly_stats && analysis.monthly_stats.length > 0 && (
        <Card>
          <h3 className="font-semibold text-[var(--color-text)] mb-3">Monthly Cashflow</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="text-left py-2 px-3 text-xs uppercase text-[var(--color-text-muted)] font-semibold">Month</th>
                  <th className="text-right py-2 px-3 text-xs uppercase text-[var(--color-text-muted)] font-semibold">Inflow</th>
                  <th className="text-right py-2 px-3 text-xs uppercase text-[var(--color-text-muted)] font-semibold">Outflow</th>
                  <th className="text-right py-2 px-3 text-xs uppercase text-[var(--color-text-muted)] font-semibold">Net</th>
                  <th className="text-right py-2 px-3 text-xs uppercase text-[var(--color-text-muted)] font-semibold">Min Balance</th>
                  <th className="text-center py-2 px-3 text-xs uppercase text-[var(--color-text-muted)] font-semibold"></th>
                </tr>
              </thead>
              <tbody>
                {analysis.monthly_stats.map((row) => {
                  const isNegativeNet = row.net < 0;
                  const isLowBalance = row.min_balance != null && row.min_balance < 100;
                  const rowClass = isNegativeNet || isLowBalance
                    ? 'bg-red-50/50 dark:bg-red-950/10'
                    : '';

                  return (
                    <React.Fragment key={row.month}>
                      <tr
                        className={`border-b border-[var(--color-border)]/50 hover:bg-[var(--color-bg)] cursor-pointer ${rowClass}`}
                        onClick={() => setExpandedMonth(expandedMonth === row.month ? null : row.month)}
                      >
                        <td className="py-2 px-3 font-medium text-[var(--color-text)]">{row.month}</td>
                        <td className="py-2 px-3 text-right text-green-600 dark:text-green-400">{fmt(row.total_inflow)}</td>
                        <td className="py-2 px-3 text-right text-red-600 dark:text-red-400">{fmt(row.total_outflow)}</td>
                        <td className={`py-2 px-3 text-right font-semibold ${row.net >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                          {row.net >= 0 ? '+' : ''}{fmt(row.net)}
                        </td>
                        <td className={`py-2 px-3 text-right ${isLowBalance ? 'text-red-600 dark:text-red-400 font-semibold' : 'text-[var(--color-text-muted)]'}`}>
                          {row.min_balance != null ? fmt(row.min_balance) : '-'}
                        </td>
                        <td className="py-2 px-3 text-center text-[var(--color-text-muted)]">
                          {expandedMonth === row.month ? '\u25B2' : '\u25BC'}
                        </td>
                      </tr>
                      {expandedMonth === row.month && analysis.cashflow_data && (
                        <tr>
                          <td colSpan={6} className="px-3 py-2 bg-[var(--color-bg)]">
                            <div className="grid grid-cols-2 gap-4 py-2">
                              <div>
                                <p className="text-xs font-semibold text-green-600 dark:text-green-400 uppercase mb-1">Inflows</p>
                                {Object.entries(analysis.cashflow_data.inflows || {}).filter(([, v]) => v > 0).map(([k, v]) => (
                                  <div key={k} className="flex justify-between text-xs py-0.5">
                                    <span className="text-[var(--color-text-muted)] capitalize">{k.replace(/_/g, ' ')}</span>
                                    <span className="text-green-600 dark:text-green-400">{fmt(v)}</span>
                                  </div>
                                ))}
                              </div>
                              <div>
                                <p className="text-xs font-semibold text-red-600 dark:text-red-400 uppercase mb-1">Outflows</p>
                                {Object.entries(analysis.cashflow_data.outflows || {}).filter(([, v]) => v > 0).map(([k, v]) => (
                                  <div key={k} className="flex justify-between text-xs py-0.5">
                                    <span className={`capitalize ${k === 'gambling_betting' ? 'text-red-500 font-semibold' : 'text-[var(--color-text-muted)]'}`}>
                                      {k.replace(/_/g, ' ')}
                                    </span>
                                    <span className={k === 'gambling_betting' ? 'text-red-500 font-semibold' : 'text-red-600 dark:text-red-400'}>{fmt(v)}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
          {/* Legend */}
          <div className="flex items-center space-x-4 mt-3 text-[10px] text-[var(--color-text-muted)]">
            <span className="flex items-center"><span className="w-2 h-2 rounded-full bg-red-400 mr-1" /> Negative net or low balance month</span>
            <span>Click a row to see category breakdown</span>
          </div>
        </Card>
      )}

      {/* Category Breakdown (always visible) */}
      {analysis.cashflow_data && (
        <Card>
          <h3 className="font-semibold text-[var(--color-text)] mb-3">Overall Category Breakdown</h3>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <p className="text-xs font-semibold text-green-600 dark:text-green-400 uppercase mb-2">Inflows</p>
              <div className="space-y-1">
                {Object.entries(analysis.cashflow_data.inflows || {})
                  .sort(([, a], [, b]) => b - a)
                  .map(([k, v]) => {
                    const total = Object.values(analysis.cashflow_data!.inflows || {}).reduce((s, x) => s + x, 0);
                    const pct = total > 0 ? (v / total) * 100 : 0;
                    return (
                      <div key={k}>
                        <div className="flex justify-between text-xs mb-0.5">
                          <span className="text-[var(--color-text-muted)] capitalize">{k.replace(/_/g, ' ')}</span>
                          <span className="text-[var(--color-text)]">{fmt(v)} <span className="text-[var(--color-text-muted)]">({pct.toFixed(0)}%)</span></span>
                        </div>
                        <div className="h-1.5 rounded-full bg-[var(--color-border)] overflow-hidden">
                          <div className="h-full rounded-full bg-green-400" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
            <div>
              <p className="text-xs font-semibold text-red-600 dark:text-red-400 uppercase mb-2">Outflows</p>
              <div className="space-y-1">
                {Object.entries(analysis.cashflow_data.outflows || {})
                  .sort(([, a], [, b]) => b - a)
                  .filter(([, v]) => v > 0)
                  .map(([k, v]) => {
                    const total = Object.values(analysis.cashflow_data!.outflows || {}).reduce((s, x) => s + x, 0);
                    const pct = total > 0 ? (v / total) * 100 : 0;
                    const isGambling = k === 'gambling_betting';
                    return (
                      <div key={k}>
                        <div className="flex justify-between text-xs mb-0.5">
                          <span className={`capitalize ${isGambling ? 'text-red-500 font-semibold' : 'text-[var(--color-text-muted)]'}`}>
                            {k.replace(/_/g, ' ')}
                          </span>
                          <span className={isGambling ? 'text-red-500 font-semibold' : 'text-[var(--color-text)]'}>
                            {fmt(v)} <span className="text-[var(--color-text-muted)]">({pct.toFixed(0)}%)</span>
                          </span>
                        </div>
                        <div className="h-1.5 rounded-full bg-[var(--color-border)] overflow-hidden">
                          <div className={`h-full rounded-full ${isGambling ? 'bg-red-500' : 'bg-red-400'}`} style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          </div>
        </Card>
      )}

      {error && <p className="text-sm text-[var(--color-danger)]">{error}</p>}
    </div>
  );
}


