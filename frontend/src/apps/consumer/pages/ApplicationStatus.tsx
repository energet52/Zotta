import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, FileText, Clock, CheckCircle, XCircle, DollarSign } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { getStatusBadge } from '../../../components/ui/Badge';
import { loanApi } from '../../../api/endpoints';

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

  useEffect(() => {
    if (!id) return;
    Promise.all([
      loanApi.get(parseInt(id)),
      loanApi.listDocuments(parseInt(id)),
    ]).then(([appRes, docRes]) => {
      setApplication(appRes.data);
      setDocuments(docRes.data);
    }).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="text-center py-12 text-gray-400">Loading...</div>;
  if (!application) return <div className="text-center py-12 text-red-500">Application not found</div>;

  const getStepStatus = (stepKey: string) => {
    const statusOrder = ['draft', 'submitted', 'under_review', 'credit_check', 'decision_pending', 'approved', 'declined'];
    const currentIdx = statusOrder.indexOf(application.status);
    const stepIdx = statusOrder.indexOf(stepKey);

    if (stepKey === 'decided') {
      return ['approved', 'declined', 'offer_sent', 'accepted', 'disbursed'].includes(application.status) ? 'complete' : 'pending';
    }
    if (stepIdx < currentIdx) return 'complete';
    if (stepIdx === currentIdx) return 'current';
    return 'pending';
  };

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
              <span className="font-medium capitalize">{application.purpose.replace('_', ' ')}</span>
            </div>
          </div>
        </Card>

        {application.status === 'approved' && (
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
              <div className="flex justify-between">
                <span className="text-green-700">Monthly Payment</span>
                <span className="font-bold text-green-800">TTD {application.monthly_payment?.toLocaleString()}</span>
              </div>
              <div className="flex gap-2 mt-4">
                <Button size="sm" className="flex-1">Accept Offer</Button>
                <Button size="sm" variant="outline" className="flex-1">Decline</Button>
              </div>
            </div>
          </Card>
        )}

        {application.status === 'declined' && (
          <Card className="border-red-200 bg-red-50">
            <h3 className="font-semibold text-red-800 mb-2">Application Declined</h3>
            <p className="text-sm text-red-700">
              Unfortunately, your application was not approved at this time.
              You may reapply after 30 days or contact us for more information.
            </p>
          </Card>
        )}
      </div>

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
                    <p className="text-xs text-gray-500 capitalize">{doc.document_type.replace('_', ' ')}</p>
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
