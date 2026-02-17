import { useEffect, useRef, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, FileText, Clock, CheckCircle, DollarSign, ArrowRightLeft, PenTool, Download, Paperclip, Trash2, Calendar, MessageSquare, XCircle, AlertTriangle } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import Badge, { getStatusBadge } from '../../../components/ui/Badge';
import { loanApi, paymentsApi } from '../../../api/endpoints';
import { useAuthStore } from '../../../store/authStore';
import { useNotificationStore } from '../../../store/notificationStore';
import ContractSignature from '../../../components/ContractSignature';

interface ApplicationItem {
  id: number;
  category_name?: string | null;
  description?: string | null;
  price: number;
  quantity: number;
}

interface Application {
  id: number;
  reference_number: string;
  amount_requested: number;
  term_months: number;
  purpose: string;
  purpose_description: string | null;
  status: string;
  interest_rate: number | null;
  amount_approved: number | null;
  monthly_payment: number | null;
  proposed_amount: number | null;
  proposed_rate: number | null;
  proposed_term: number | null;
  counterproposal_reason: string | null;
  contract_signed_at: string | null;
  contract_typed_name: string | null;
  submitted_at: string | null;
  decided_at: string | null;
  created_at: string;
  merchant_name?: string | null;
  branch_name?: string | null;
  credit_product_name?: string | null;
  downpayment?: number | null;
  total_financed?: number | null;
  items?: ApplicationItem[];
}

interface DocumentInfo {
  id: number;
  document_type: string;
  file_name: string;
  status: string;
}

const STATUS_STEPS = [
  { key: 'submitted', label: 'Submitted', icon: FileText },
  { key: 'under_review', label: 'Under Review', icon: Clock },
  { key: 'credit_check', label: 'Credit Check', icon: DollarSign },
  { key: 'decided', label: 'Decision', icon: CheckCircle },
];

export default function ApplicationStatus() {
  const { id } = useParams<{ id: string }>();
  const [application, setApplication] = useState<Application | null>(null);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState('');
  const [showContract, setShowContract] = useState(false);
  const [docUploadType, setDocUploadType] = useState('other');
  const [docUploadFile, setDocUploadFile] = useState<File | null>(null);
  const [docUploading, setDocUploading] = useState(false);
  const [docUploadError, setDocUploadError] = useState('');
  const [docDeleting, setDocDeleting] = useState<number | null>(null);
  const [schedule, setSchedule] = useState<any[]>([]);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [profile, setProfile] = useState<any>(null);
  const [comments, setComments] = useState<any[]>([]);
  const [newComment, setNewComment] = useState('');
  const [addingComment, setAddingComment] = useState(false);
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const autoAcceptDone = useRef(false);
  const user = useAuthStore((s) => s.user);
  const commentsEndRef = useRef<HTMLDivElement>(null);

  const CANCELLABLE_STATUSES = ['draft', 'submitted', 'under_review', 'awaiting_documents', 'credit_check', 'decision_pending', 'counter_proposed'];
  const FINAL_STATUSES = ['declined', 'rejected_by_applicant', 'disbursed', 'cancelled', 'voided', 'approved'];
  const canUploadDocuments = application && !FINAL_STATUSES.includes(application.status);

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
    // Also load profile for contract signing and comments
    loanApi.getProfile().then(res => setProfile(res.data)).catch(() => {});
    loanApi.listComments(parseInt(id)).then(res => {
      setComments(res.data || []);
      // Mark staff messages as read when viewing the application
      loanApi.markCommentsRead(parseInt(id)).then(() => {
        useNotificationStore.getState().fetch();
      }).catch(() => {});
    }).catch(() => {});
    Promise.all([
      loanApi.get(parseInt(id)),
      loanApi.listDocuments(parseInt(id)),
    ]).then(([appRes, docRes]) => {
      setApplication(appRes.data);
      setDocuments(docRes.data);
      // Always try to load payment schedule
      setScheduleLoading(true);
      paymentsApi.getSchedule(parseInt(id))
        .then((sRes) => setSchedule(sRes.data || []))
        .catch(() => setSchedule([]))
        .finally(() => setScheduleLoading(false));
    }).finally(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, [id]);

  useEffect(() => { autoAcceptDone.current = false; }, [id]);

  // Auto-accept when approved/offer_sent (skip explicit Accept Offer step; counter proposal keeps its own Accept/Reject)
  useEffect(() => {
    if (!application || !id || autoAcceptDone.current) return;
    if (application.status !== 'approved' && application.status !== 'offer_sent') return;
    autoAcceptDone.current = true;
    setActionLoading('accept');
    loanApi.acceptOffer(application.id)
      .then(loadData)
      .catch(() => { autoAcceptDone.current = false; })
      .finally(() => setActionLoading(''));
  }, [application?.id, application?.status, id]);

  const handleAcceptCounterproposal = async () => {
    if (!application) return;
    setActionLoading('accept_cp');
    try {
      await loanApi.acceptCounterproposal(application.id);
      loadData();
    } catch {} finally { setActionLoading(''); }
  };

  const handleRejectCounterproposal = async () => {
    if (!application) return;
    setActionLoading('reject_cp');
    try {
      await loanApi.rejectCounterproposal(application.id);
      loadData();
    } catch {} finally { setActionLoading(''); }
  };

  const handleCancelApplication = async () => {
    if (!application) return;
    setActionLoading('cancel');
    try {
      await loanApi.cancel(application.id, cancelReason);
      setShowCancelDialog(false);
      setCancelReason('');
      loadData();
    } catch {} finally { setActionLoading(''); }
  };

  const handleContractSigned = () => {
    setShowContract(false);
    loadData();
  };

  const handleAddComment = async () => {
    if (!id || !newComment.trim()) return;
    setAddingComment(true);
    try {
      const res = await loanApi.addComment(parseInt(id), newComment.trim());
      setComments(prev => [...prev, res.data]);
      setNewComment('');
      setTimeout(() => commentsEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
    } catch { /* ignore */ }
    setAddingComment(false);
  };

  const handleDocUpload = async () => {
    if (!id || !docUploadFile || !application) return;
    setDocUploading(true); setDocUploadError('');
    try {
      const formData = new FormData();
      formData.append('document_type', docUploadType);
      formData.append('file', docUploadFile);
      await loanApi.uploadDocument(parseInt(id), formData);
      setDocUploadFile(null);
      loadData();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setDocUploadError(typeof detail === 'string' ? detail : 'Upload failed');
    } finally { setDocUploading(false); }
  };

  const handleDocDownload = async (docId: number, fileName: string) => {
    if (!id) return;
    try {
      const res = await loanApi.downloadDocument(parseInt(id), docId);
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
      await loanApi.deleteDocument(parseInt(id), docId);
      loadData();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setDocUploadError(typeof detail === 'string' ? detail : 'Delete failed');
    } finally { setDocDeleting(null); }
  };

  const handleDownloadConsent = async () => {
    if (!id) return;
    try {
      const res = await loanApi.getConsentPdf(parseInt(id));
      const blob = res.data instanceof Blob ? res.data : new Blob([res.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `hire-purchase-agreement-${application?.reference_number || id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* ignore */ }
  };

  if (loading) return <div className="text-center py-12 text-[var(--color-text-muted)]">Loading...</div>;
  if (!application) return <div className="text-center py-12 text-[var(--color-danger)]">Application not found</div>;

  const getStepStatus = (stepKey: string) => {
    const statusOrder = ['draft', 'submitted', 'under_review', 'credit_check', 'decision_pending', 'approved', 'declined'];
    const currentIdx = statusOrder.indexOf(application.status);
    const stepIdx = statusOrder.indexOf(stepKey);

    if (stepKey === 'decided') {
      return ['approved', 'declined', 'offer_sent', 'accepted', 'disbursed', 'counter_proposed'].includes(application.status) ? 'complete' : 'pending';
    }
    if (stepIdx < currentIdx) return 'complete';
    if (stepIdx === currentIdx) return 'current';
    return 'pending';
  };

  const needsContractSignature = ['approved', 'offer_sent', 'accepted'].includes(application.status) && !application.contract_signed_at;

  return (
    <div className="max-w-3xl mx-auto">
      <Link to="/dashboard" className="inline-flex items-center text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] mb-4">
        <ArrowLeft size={16} className="mr-1" /> Back to Dashboard
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">{application.reference_number}</h1>
          <p className="text-[var(--color-text-muted)] mt-1">Submitted {application.submitted_at ? new Date(application.submitted_at).toLocaleDateString() : 'N/A'}</p>
        </div>
        {getStatusBadge(application.status)}
      </div>

      {/* Progress tracker */}
      <Card className="mb-6">
        <h2 className="text-lg font-semibold mb-6">Application Progress</h2>
        <div className="flex items-center justify-between">
          {STATUS_STEPS.map(({ key, label, icon: Icon }, i) => {
            const status = getStepStatus(key);
            return (
              <div key={key} className="flex items-center flex-1">
                <div className="flex flex-col items-center">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center
                    ${status === 'complete' ? 'bg-green-500 text-white' :
                      status === 'current' ? 'bg-[var(--color-primary)] text-white' :
                      'bg-[var(--color-border)] text-[var(--color-text-muted)]'}`}>
                    {status === 'complete' ? <CheckCircle size={20} /> : <Icon size={20} />}
                  </div>
                  <span className="text-xs mt-2 text-center">{label}</span>
                </div>
                {i < STATUS_STEPS.length - 1 && (
                  <div className={`flex-1 h-0.5 mx-2 ${status === 'complete' ? 'bg-[var(--color-success)]' : 'bg-[var(--color-border)]'}`} />
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* Loan details — Shopping + Plan Selection (same as backoffice) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <Card>
          <h3 className="font-semibold mb-4">Loan Details</h3>
          <div className="space-y-4">
            {/* Shopping Context */}
            {(application.merchant_name || application.branch_name || (application.items && application.items.length > 0)) && (
              <div className="p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
                <h5 className="text-xs font-medium text-[var(--color-text-muted)] uppercase mb-2">Shopping Context</h5>
                <div className="space-y-2 text-sm mb-3">
                  <div className="flex justify-between">
                    <span className="text-[var(--color-text-muted)]">Merchant</span>
                    <span className="font-medium">{application.merchant_name || '—'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--color-text-muted)]">Branch</span>
                    <span className="font-medium">{application.branch_name || '—'}</span>
                  </div>
                </div>
                {application.items && application.items.length > 0 && (
                  <>
                    <h5 className="text-xs font-medium text-[var(--color-text-muted)] uppercase mb-2">Items</h5>
                    <div className="overflow-x-auto mb-2">
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
                          {application.items.map((it) => (
                            <tr key={it.id} className="border-b border-[var(--color-border)]/50">
                              <td className="py-2 pr-2">{it.category_name || '—'}</td>
                              <td className="py-2 pr-2">TTD {(it.price || 0).toLocaleString()}</td>
                              <td className="py-2 pr-2">{it.quantity}</td>
                              <td className="py-2 pr-2">{it.description || '—'}</td>
                              <td className="py-2 font-medium">TTD {((it.price || 0) * (it.quantity || 1)).toLocaleString()}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <p className="text-sm">
                      <span className="text-[var(--color-text-muted)]">Total Purchase:</span>{' '}
                      <span className="font-bold">
                        TTD {application.items.reduce((s, it) => s + (it.price || 0) * (it.quantity || 1), 0).toLocaleString()}
                      </span>
                    </p>
                  </>
                )}
              </div>
            )}
            {/* Plan Selection */}
            <div className="p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
              <h5 className="text-xs font-medium text-[var(--color-text-muted)] uppercase mb-2">Plan Selection</h5>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Credit Product</span>
                  <span className="font-medium">{application.credit_product_name || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Term</span>
                  <span className="font-medium">{application.term_months} months</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Total Financed</span>
                  <span className="font-medium">TTD {(application.total_financed ?? application.amount_requested).toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Downpayment</span>
                  <span className="font-medium">TTD {(application.downpayment ?? 0).toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Monthly Payment</span>
                  <span className="font-medium text-[var(--color-primary)]">TTD {(application.monthly_payment ?? 0).toLocaleString()}</span>
                </div>
              </div>
            </div>
            {/* Standard fields */}
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-[var(--color-text-muted)]">Amount Requested</span>
                <span className="font-medium">TTD {application.amount_requested.toLocaleString()}</span>
              </div>
              {/* purpose hidden — single product for now */}
            </div>
            {application.contract_signed_at && (
              <div className="pt-2 border-t border-[var(--color-border)] space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-[var(--color-text-muted)]">Hire Purchase Agreement and Consent</span>
                  <Button size="sm" variant="outline" onClick={handleDownloadConsent}>
                    <Download size={14} className="mr-1" /> Download PDF
                  </Button>
                </div>
                <p className="text-xs text-[var(--color-text-muted)]">
                  Signed on {new Date(application.contract_signed_at).toLocaleString()}
                  {application.contract_typed_name && ` by ${application.contract_typed_name}`}
                </p>
              </div>
            )}
          </div>
        </Card>

        {/* Counterproposal Card */}
        {application.status === 'counter_proposed' && (
          <Card className="border-purple-200 bg-purple-50">
            <h3 className="font-semibold text-purple-800 mb-2 flex items-center">
              <ArrowRightLeft size={18} className="mr-2" />
              Counterproposal Received
            </h3>
            <p className="text-sm text-purple-700 mb-4">
              The underwriter has proposed different terms for your loan:
            </p>

            {/* Comparison Table */}
            <div className="space-y-2 text-sm mb-4">
              <div className="flex justify-between items-center">
                <span className="text-purple-600">Amount</span>
                <div className="flex items-center space-x-3">
                  <span className="text-[var(--color-text-muted)] line-through">TTD {application.amount_requested.toLocaleString()}</span>
                  <span className="font-bold text-purple-800">TTD {application.proposed_amount?.toLocaleString()}</span>
                </div>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-purple-600">Interest Rate</span>
                <span className="font-bold text-purple-800">{application.proposed_rate}%</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-purple-600">Term</span>
                <div className="flex items-center space-x-3">
                  {application.proposed_term !== application.term_months && (
                    <span className="text-[var(--color-text-muted)] line-through">{application.term_months}m</span>
                  )}
                  <span className="font-bold text-purple-800">{application.proposed_term} months</span>
                </div>
              </div>
            </div>

            {application.counterproposal_reason && (
              <div className="p-2 bg-white/50 rounded-lg mb-4">
                <p className="text-xs text-purple-600 font-medium mb-1">Reason:</p>
                <p className="text-sm text-purple-800">{application.counterproposal_reason}</p>
              </div>
            )}

            <div className="flex gap-2">
              <Button
                size="sm"
                className="flex-1"
                onClick={handleAcceptCounterproposal}
                isLoading={actionLoading === 'accept_cp'}
              >
                Accept
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="flex-1"
                onClick={handleRejectCounterproposal}
                isLoading={actionLoading === 'reject_cp'}
              >
                Reject
              </Button>
            </div>
          </Card>
        )}

        {/* Approved Offer Card - auto-accepted (no explicit Accept/Decline except for counter proposal) */}
        {(application.status === 'approved' || application.status === 'offer_sent') && (
          <Card className="border-green-200 bg-green-50">
            <h3 className="font-semibold text-green-800 mb-4">Approved Offer</h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-green-700">Approved Amount</span>
                <span className="font-bold text-green-800">TTD {application.amount_approved?.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-green-700">Interest Rate</span>
                <span className="font-bold text-green-800">{application.interest_rate}%</span>
              </div>
              {application.monthly_payment && (
                <div className="flex justify-between">
                  <span className="text-green-700">Monthly Payment</span>
                  <span className="font-bold text-green-800">TTD {application.monthly_payment?.toLocaleString()}</span>
                </div>
              )}
              <div className="mt-4">
                {actionLoading === 'accept' ? (
                  <p className="text-green-700">Confirming your offer...</p>
                ) : needsContractSignature ? (
                  <Button size="sm" className="w-full" onClick={() => setShowContract(true)}>
                    <PenTool size={14} className="mr-1" /> Sign Contract
                  </Button>
                ) : (
                  <p className="text-green-700">Your offer has been confirmed.</p>
                )}
              </div>
            </div>
          </Card>
        )}

        {/* Accepted / Contract Signed */}
        {application.status === 'accepted' && (
          <Card className="border-green-200 bg-green-50">
            <h3 className="font-semibold text-green-800 mb-2">Offer Accepted</h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-green-700">Approved Amount</span>
                <span className="font-bold text-green-800">TTD {application.amount_approved?.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-green-700">Interest Rate</span>
                <span className="font-bold text-green-800">{application.interest_rate}%</span>
              </div>
              {application.contract_signed_at && (
                <div className="p-2 bg-white/50 rounded-lg mt-2">
                  <p className="text-xs text-green-600 font-medium">Contract signed on {new Date(application.contract_signed_at).toLocaleString()}</p>
                  <p className="text-xs text-green-700">by {application.contract_typed_name}</p>
                </div>
              )}
              {needsContractSignature && (
                <Button size="sm" className="w-full mt-2" onClick={() => setShowContract(true)}>
                  <PenTool size={14} className="mr-1" /> Sign Contract
                </Button>
              )}
            </div>
          </Card>
        )}

        {/* Disbursed */}
        {application.status === 'disbursed' && (
          <Card className="border-cyan-200 bg-cyan-50">
            <h3 className="font-semibold text-cyan-800 mb-2">Loan Disbursed</h3>
            <p className="text-sm text-cyan-700">
              Your loan has been disbursed. Funds should be available in your account.
            </p>
            <div className="space-y-2 text-sm mt-3">
              <div className="flex justify-between">
                <span className="text-cyan-700">Disbursed Amount</span>
                <span className="font-bold text-cyan-800">TTD {application.amount_approved?.toLocaleString()}</span>
              </div>
              {application.monthly_payment && (
                <div className="flex justify-between">
                  <span className="text-cyan-700">Monthly Payment</span>
                  <span className="font-bold text-cyan-800">TTD {application.monthly_payment?.toLocaleString()}</span>
                </div>
              )}
            </div>
          </Card>
        )}

        {/* Declined */}
        {application.status === 'declined' && (
          <Card className="border-red-200 bg-red-50">
            <h3 className="font-semibold text-red-800 mb-2">Application Declined</h3>
            <p className="text-sm text-red-700">
              Unfortunately, your application was not approved at this time.
              You may reapply after 30 days or contact us for more information.
            </p>
          </Card>
        )}

        {/* Rejected by Applicant */}
        {application.status === 'rejected_by_applicant' && (
          <Card className="border-[var(--color-border)] bg-[var(--color-surface-hover)]">
            <h3 className="font-semibold text-[var(--color-text)] mb-2">Offer Declined</h3>
            <p className="text-sm text-[var(--color-text-muted)]">
              You have declined the loan offer. You may submit a new application if needed.
            </p>
          </Card>
        )}

        {/* Cancelled */}
        {application.status === 'cancelled' && (
          <Card className="border-orange-200 bg-orange-50">
            <h3 className="font-semibold text-orange-800 mb-2 flex items-center">
              <XCircle size={18} className="mr-2" />
              Application Cancelled
            </h3>
            <p className="text-sm text-orange-700">
              You cancelled this application. You may submit a new application at any time.
            </p>
          </Card>
        )}

        {/* Voided */}
        {application.status === 'voided' && (
          <Card className="border-red-200 bg-red-50">
            <h3 className="font-semibold text-red-800 mb-2 flex items-center">
              <XCircle size={18} className="mr-2" />
              Application Voided
            </h3>
            <p className="text-sm text-red-700">
              This application has been voided by staff. Please contact us if you have questions.
            </p>
          </Card>
        )}

        {/* Cancel Application Button */}
        {CANCELLABLE_STATUSES.includes(application.status) && (
          <div className="pt-2">
            <button
              onClick={() => setShowCancelDialog(true)}
              className="text-sm text-red-500 hover:text-red-700 underline"
            >
              Cancel this application
            </button>
          </div>
        )}
      </div>

      {/* Cancel Confirmation Dialog */}
      {showCancelDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-[var(--color-surface)] rounded-xl shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-[var(--color-text)] mb-2 flex items-center">
              <AlertTriangle size={20} className="mr-2 text-orange-500" />
              Cancel Application
            </h3>
            <p className="text-sm text-[var(--color-text-muted)] mb-4">
              Are you sure you want to cancel this application? This action cannot be undone.
            </p>
            <div className="mb-4">
              <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">
                Reason (optional)
              </label>
              <textarea
                value={cancelReason}
                onChange={e => setCancelReason(e.target.value)}
                className="w-full border border-[var(--color-border)] rounded-lg px-3 py-2 text-sm bg-[var(--color-surface)] text-[var(--color-text)] resize-none"
                rows={3}
                placeholder="Why are you cancelling?"
              />
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                className="flex-1"
                onClick={() => { setShowCancelDialog(false); setCancelReason(''); }}
              >
                Keep Application
              </Button>
              <Button
                size="sm"
                className="flex-1 !bg-red-600 hover:!bg-red-700"
                onClick={handleCancelApplication}
                isLoading={actionLoading === 'cancel'}
              >
                Yes, Cancel
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Contract Signature Modal */}
      {showContract && application && (
        <ContractSignature
          applicationId={application.id}
          loanAmount={application.amount_approved || application.proposed_amount || application.amount_requested}
          interestRate={application.interest_rate || application.proposed_rate || 0}
          termMonths={application.proposed_term || application.term_months}
          monthlyPayment={application.monthly_payment || 0}
          applicantName={user ? `${user.first_name} ${user.last_name}` : ''}
          applicantAddress={profile ? [profile.address_line1, profile.address_line2, profile.city, profile.parish].filter(Boolean).join(', ') : ''}
          referenceNumber={application.reference_number}
          downpayment={application.downpayment || 0}
          totalFinanced={application.total_financed || application.amount_approved || application.amount_requested}
          productName={application.credit_product_name || 'Hire Purchase'}
          items={application.items?.map(it => ({
            description: it.description || it.category_name || '',
            category_name: it.category_name || '',
            quantity: it.quantity || 1,
            price: it.price || 0,
          }))}
          onSigned={handleContractSigned}
          onCancel={() => setShowContract(false)}
        />
      )}

      {/* Payment Schedule – for all applications with known amounts */}
      {application && (() => {
        const loanAmt = Number(application.amount_approved || application.amount_requested || 0);
        const rate = Number(application.interest_rate || 0);
        const term = Number(application.term_months || 0);
        const displaySchedule = schedule.length > 0 ? schedule : computeProjectedSchedule(loanAmt, rate, term);
        const isProjected = schedule.length === 0 && displaySchedule.length > 0;
        if (scheduleLoading) return <Card className="mt-6"><p className="text-sm text-[var(--color-text-muted)]">Loading schedule...</p></Card>;
        if (displaySchedule.length === 0) return null;
        return (
          <Card className="mt-6">
            <h3 className="font-semibold text-[var(--color-text)] mb-4 flex items-center">
              <Calendar size={18} className="mr-2 text-[var(--color-primary)]" />
              Payment Schedule
              {isProjected && <Badge variant="warning" className="ml-2 text-[10px]">Estimated</Badge>}
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <div className="p-3 rounded-lg bg-[var(--color-bg)]">
                <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Loan Amount</p>
                <p className="text-lg font-bold text-[var(--color-text)]">TTD {loanAmt.toLocaleString()}</p>
              </div>
              <div className="p-3 rounded-lg bg-[var(--color-bg)]">
                <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Total Interest</p>
                <p className="text-lg font-bold text-[var(--color-text)]">TTD {displaySchedule.reduce((s: number, r: any) => s + Number(r.interest || 0), 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
              </div>
              <div className="p-3 rounded-lg bg-[var(--color-bg)]">
                <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Total Fees</p>
                <p className="text-lg font-bold text-[var(--color-text)]">TTD {displaySchedule.reduce((s: number, r: any) => s + Number(r.fee || 0), 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
              </div>
              <div className="p-3 rounded-lg bg-[var(--color-bg)]">
                <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">Total Payable</p>
                <p className="text-lg font-bold text-[var(--color-primary)]">TTD {displaySchedule.reduce((s: number, r: any) => s + Number(r.amount_due || 0), 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
              </div>
            </div>
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
                      <td className="px-3 py-2 text-right text-[var(--color-text)]">TTD {Number(row.principal || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                      <td className="px-3 py-2 text-right text-[var(--color-text)]">TTD {Number(row.interest || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                      <td className="px-3 py-2 text-right font-medium text-[var(--color-text)]">TTD {Number(row.amount_due || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                      {!isProjected && <td className="px-3 py-2 text-right text-[var(--color-text)]">TTD {Number(row.amount_paid || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>}
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
                This is an estimated schedule based on your current loan terms. The actual schedule will be confirmed upon disbursement.
              </p>
            )}
          </Card>
        );
      })()}

      {/* Online Payment for Disbursed Loans */}
      {application && application.status === 'disbursed' && (
        <ConsumerPaymentSection applicationId={application.id} monthlyPayment={application.monthly_payment || 0} />
      )}

      {/* Documents */}
      <Card>
        <h3 className="font-semibold mb-4">Documents</h3>

        {canUploadDocuments && (
          <div className="mb-4 p-4 rounded-lg bg-[var(--color-bg)] space-y-3">
            <p className="text-sm text-[var(--color-text-muted)]">Upload additional documents to support your application.</p>
            <div className="flex flex-wrap gap-3 items-end">
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
                  onChange={(e) => { setDocUploadFile(e.target.files?.[0] || null); setDocUploadError(''); }}
                  className="block w-full text-sm text-[var(--color-text-muted)] file:mr-2 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-[var(--color-primary)] file:text-white file:cursor-pointer"
                />
              </div>
              <Button size="sm" onClick={handleDocUpload} isLoading={docUploading} disabled={!docUploadFile}>
                <Paperclip size={14} className="mr-1" /> Upload
              </Button>
            </div>
            {docUploadError && <p className="text-sm text-[var(--color-danger)]">{docUploadError}</p>}
          </div>
        )}

        <h4 className="font-medium mb-2">Uploaded Documents</h4>
        {documents.length > 0 ? (
          <div className="space-y-2">
            {documents.map((doc) => (
              <div key={doc.id} className="flex items-center justify-between py-2 border-b border-[var(--color-border)] last:border-0">
                <div className="flex items-center space-x-3">
                  <FileText size={18} className="text-[var(--color-text-muted)]" />
                  <div>
                    <p className="text-sm font-medium text-[var(--color-text)]">{doc.file_name}</p>
                    <p className="text-xs text-[var(--color-text-muted)] capitalize">{doc.document_type.replace(/_/g, ' ')}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {getStatusBadge(doc.status)}
                  <Button size="sm" variant="ghost" onClick={() => handleDocDownload(doc.id, doc.file_name)}>
                    <Download size={14} />
                  </Button>
                  {canUploadDocuments && (
                    <Button size="sm" variant="ghost" onClick={() => handleDocDelete(doc.id)} isLoading={docDeleting === doc.id}>
                      <Trash2 size={14} className="text-[var(--color-danger)]" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-[var(--color-text-muted)]">No documents uploaded yet</p>
        )}
      </Card>

      {/* Comments / Messages */}
      <Card>
        <h3 className="font-semibold mb-4 flex items-center">
          <MessageSquare size={18} className="mr-2 text-[var(--color-primary)]" />
          Messages
        </h3>
        <p className="text-xs text-[var(--color-text-muted)] mb-3">
          Use this section to communicate with the underwriting team. They will see your messages and can respond here.
        </p>

        {/* Messages list */}
        <div className="space-y-3 max-h-80 overflow-y-auto mb-4 border border-[var(--color-border)] rounded-lg p-3 bg-[var(--color-bg)]">
          {comments.length === 0 ? (
            <p className="text-sm text-[var(--color-text-muted)] text-center py-4">No messages yet. Send a message below.</p>
          ) : (
            comments.map((c: any) => (
              <div
                key={c.id}
                className={`flex ${c.is_from_applicant ? 'justify-end' : 'justify-start'}`}
              >
                <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                  c.is_from_applicant
                    ? 'bg-[var(--color-primary)] text-white rounded-br-none'
                    : 'bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text)] rounded-bl-none'
                }`}>
                  {!c.is_from_applicant && (
                    <p className="text-[10px] font-semibold mb-0.5 opacity-70">{c.author_name} (Staff)</p>
                  )}
                  <p className="whitespace-pre-wrap">{c.content}</p>
                  <p className={`text-[10px] mt-1 ${c.is_from_applicant ? 'text-white/70' : 'text-[var(--color-text-muted)]'}`}>
                    {c.created_at ? new Date(c.created_at).toLocaleString() : ''}
                  </p>
                </div>
              </div>
            ))
          )}
          <div ref={commentsEndRef} />
        </div>

        {/* Add comment */}
        <div className="flex gap-2">
          <input
            type="text"
            className="flex-1 px-3 py-2 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/40"
            placeholder="Type your message..."
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && newComment.trim()) {
                e.preventDefault();
                handleAddComment();
              }
            }}
          />
          <Button
            size="sm"
            disabled={addingComment || !newComment.trim()}
            onClick={handleAddComment}
          >
            {addingComment ? '...' : 'Send'}
          </Button>
        </div>
      </Card>
    </div>
  );
}


function ConsumerPaymentSection({ applicationId, monthlyPayment }: { applicationId: number; monthlyPayment: number }) {
  const [amount, setAmount] = useState(String(monthlyPayment || ''));
  const [paying, setPaying] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  const handlePay = async () => {
    if (!amount || parseFloat(amount) <= 0) return;
    setPaying(true);
    setError('');
    try {
      const res = await paymentsApi.payOnline(applicationId, { amount: parseFloat(amount) });
      setSuccess(`Payment of TTD ${parseFloat(amount).toLocaleString()} processed successfully! Ref: ${res.data.reference_number}`);
      setAmount(String(monthlyPayment || ''));
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (typeof detail === 'string') {
        setError(detail);
      } else if (Array.isArray(detail)) {
        setError(detail.map((e: any) => e.msg || String(e)).join('; '));
      } else {
        setError('Payment failed');
      }
    }
    setPaying(false);
  };

  return (
    <Card>
      <h3 className="font-semibold mb-4 flex items-center space-x-2">
        <DollarSign size={18} className="text-emerald-500" />
        <span>Make a Payment</span>
      </h3>
      {success && (
        <div className="mb-4 p-3 rounded-lg bg-emerald-50 text-emerald-700 text-sm">{success}</div>
      )}
      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-50 text-red-700 text-sm">{error}</div>
      )}
      <div className="flex items-end space-x-3">
        <div className="flex-1">
          <label className="block text-sm text-[var(--color-text-muted)] mb-1">Amount (TTD)</label>
          <input
            type="number"
            value={amount}
            onChange={e => setAmount(e.target.value)}
            className="w-full px-3 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:ring-2 focus:ring-[var(--color-primary)] focus:border-[var(--color-primary)]"
            min="0.01"
            step="0.01"
          />
        </div>
        <Button onClick={handlePay} isLoading={paying} disabled={!amount || parseFloat(amount) <= 0}>
          Pay Now
        </Button>
      </div>
      <p className="text-xs text-[var(--color-text-muted)] mt-2">Monthly payment: TTD {monthlyPayment.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
    </Card>
  );
}
