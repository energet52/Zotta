import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, FileText, Clock, CheckCircle, XCircle, DollarSign, ArrowRightLeft, PenTool } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { getStatusBadge } from '../../../components/ui/Badge';
import { loanApi, paymentsApi } from '../../../api/endpoints';
import ContractSignature from '../../../components/ContractSignature';

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

  const loadData = () => {
    if (!id) return;
    Promise.all([
      loanApi.get(parseInt(id)),
      loanApi.listDocuments(parseInt(id)),
    ]).then(([appRes, docRes]) => {
      setApplication(appRes.data);
      setDocuments(docRes.data);
    }).finally(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, [id]);

  const handleAcceptOffer = async () => {
    if (!application) return;
    setActionLoading('accept');
    try {
      await loanApi.acceptOffer(application.id);
      loadData();
    } catch {} finally { setActionLoading(''); }
  };

  const handleDeclineOffer = async () => {
    if (!application) return;
    setActionLoading('decline');
    try {
      await loanApi.declineOffer(application.id);
      loadData();
    } catch {} finally { setActionLoading(''); }
  };

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

  const handleContractSigned = () => {
    setShowContract(false);
    loadData();
  };

  if (loading) return <div className="text-center py-12 text-gray-400">Loading...</div>;
  if (!application) return <div className="text-center py-12 text-red-500">Application not found</div>;

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
      <Link to="/dashboard" className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-4">
        <ArrowLeft size={16} className="mr-1" /> Back to Dashboard
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{application.reference_number}</h1>
          <p className="text-gray-500 mt-1">Submitted {application.submitted_at ? new Date(application.submitted_at).toLocaleDateString() : 'N/A'}</p>
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
                      'bg-gray-200 text-gray-400'}`}>
                    {status === 'complete' ? <CheckCircle size={20} /> : <Icon size={20} />}
                  </div>
                  <span className="text-xs mt-2 text-center">{label}</span>
                </div>
                {i < STATUS_STEPS.length - 1 && (
                  <div className={`flex-1 h-0.5 mx-2 ${status === 'complete' ? 'bg-green-500' : 'bg-gray-200'}`} />
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* Loan details */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <Card>
          <h3 className="font-semibold mb-4">Loan Details</h3>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">Amount Requested</span>
              <span className="font-medium">TTD {application.amount_requested.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Term</span>
              <span className="font-medium">{application.term_months} months</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Purpose</span>
              <span className="font-medium capitalize">{application.purpose.replace(/_/g, ' ')}</span>
            </div>
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
                  <span className="text-gray-500 line-through">TTD {application.amount_requested.toLocaleString()}</span>
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
                    <span className="text-gray-500 line-through">{application.term_months}m</span>
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

        {/* Approved Offer Card */}
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
              <div className="flex gap-2 mt-4">
                {needsContractSignature ? (
                  <Button size="sm" className="flex-1" onClick={() => setShowContract(true)}>
                    <PenTool size={14} className="mr-1" /> Sign Contract & Accept
                  </Button>
                ) : (
                  <Button size="sm" className="flex-1" onClick={handleAcceptOffer} isLoading={actionLoading === 'accept'}>
                    Accept Offer
                  </Button>
                )}
                <Button size="sm" variant="outline" className="flex-1" onClick={handleDeclineOffer} isLoading={actionLoading === 'decline'}>
                  Decline
                </Button>
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
          <Card className="border-gray-200 bg-gray-50">
            <h3 className="font-semibold text-gray-800 mb-2">Offer Declined</h3>
            <p className="text-sm text-gray-700">
              You have declined the loan offer. You may submit a new application if needed.
            </p>
          </Card>
        )}
      </div>

      {/* Contract Signature Modal */}
      {showContract && application && (
        <ContractSignature
          applicationId={application.id}
          loanAmount={application.amount_approved || application.proposed_amount || application.amount_requested}
          interestRate={application.interest_rate || application.proposed_rate || 0}
          termMonths={application.proposed_term || application.term_months}
          monthlyPayment={application.monthly_payment || 0}
          onSigned={handleContractSigned}
          onCancel={() => setShowContract(false)}
        />
      )}

      {/* Online Payment for Disbursed Loans */}
      {application && application.status === 'disbursed' && (
        <ConsumerPaymentSection applicationId={application.id} monthlyPayment={application.monthly_payment || 0} />
      )}

      {/* Documents */}
      <Card>
        <h3 className="font-semibold mb-4">Uploaded Documents</h3>
        {documents.length > 0 ? (
          <div className="space-y-2">
            {documents.map((doc) => (
              <div key={doc.id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                <div className="flex items-center space-x-3">
                  <FileText size={18} className="text-gray-400" />
                  <div>
                    <p className="text-sm font-medium">{doc.file_name}</p>
                    <p className="text-xs text-gray-500 capitalize">{doc.document_type.replace(/_/g, ' ')}</p>
                  </div>
                </div>
                {getStatusBadge(doc.status)}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-500">No documents uploaded yet</p>
        )}
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
          <label className="block text-sm text-gray-600 mb-1">Amount (TTD)</label>
          <input
            type="number"
            value={amount}
            onChange={e => setAmount(e.target.value)}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            min="0.01"
            step="0.01"
          />
        </div>
        <Button onClick={handlePay} isLoading={paying} disabled={!amount || parseFloat(amount) <= 0}>
          Pay Now
        </Button>
      </div>
      <p className="text-xs text-gray-500 mt-2">Monthly payment: TTD {monthlyPayment.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
    </Card>
  );
}
