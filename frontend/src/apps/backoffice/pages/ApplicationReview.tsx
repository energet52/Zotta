import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Shield, TrendingUp, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import Badge, { getStatusBadge } from '../../../components/ui/Badge';
import { underwriterApi } from '../../../api/endpoints';

interface Decision {
  id: number;
  credit_score: number | null;
  risk_band: string | null;
  engine_outcome: string | null;
  engine_reasons: { reasons?: string[] } | null;
  scoring_breakdown: Record<string, number> | null;
  rules_results: { rules?: { name: string; passed: boolean; message: string; severity: string }[] } | null;
  suggested_rate: number | null;
  suggested_amount: number | null;
  underwriter_action: string | null;
  override_reason: string | null;
  final_outcome: string | null;
}

export default function ApplicationReview() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [application, setApplication] = useState<any>(null);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState('');
  const [reason, setReason] = useState('');
  const [approvedAmount, setApprovedAmount] = useState('');
  const [approvedRate, setApprovedRate] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!id) return;
    const appId = parseInt(id);
    Promise.all([
      underwriterApi.getApplication(appId),
      underwriterApi.getDecision(appId).catch(() => ({ data: null })),
    ]).then(([appRes, decRes]) => {
      setApplication(appRes.data);
      setDecision(decRes.data);
      if (decRes.data?.suggested_amount) setApprovedAmount(String(decRes.data.suggested_amount));
      if (decRes.data?.suggested_rate) setApprovedRate(String(decRes.data.suggested_rate));
    }).finally(() => setLoading(false));
  }, [id]);

  const handleDecide = async () => {
    if (!action || !reason) { setError('Please select an action and provide a reason'); return; }
    setSubmitting(true);
    setError('');
    try {
      await underwriterApi.decide(parseInt(id!), {
        action,
        reason,
        approved_amount: approvedAmount ? parseFloat(approvedAmount) : undefined,
        approved_rate: approvedRate ? parseFloat(approvedRate) : undefined,
      });
      navigate('/backoffice/queue');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Decision failed');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="text-center py-12 text-gray-400">Loading...</div>;
  if (!application) return <div className="text-center py-12 text-red-500">Application not found</div>;

  const riskBandColor: Record<string, string> = {
    A: 'success', B: 'success', C: 'warning', D: 'danger', E: 'danger',
  };

  return (
    <div className="max-w-5xl mx-auto">
      <Link to="/backoffice/queue" className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-4">
        <ArrowLeft size={16} className="mr-1" /> Back to Queue
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{application.reference_number}</h1>
          <p className="text-gray-500">Application Review</p>
        </div>
        {getStatusBadge(application.status)}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column - Application details */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <h2 className="text-lg font-semibold mb-4">Loan Details</h2>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><span className="text-gray-500">Amount:</span> <strong>TTD {application.amount_requested?.toLocaleString()}</strong></div>
              <div><span className="text-gray-500">Term:</span> <strong>{application.term_months} months</strong></div>
              <div><span className="text-gray-500">Purpose:</span> <strong className="capitalize">{application.purpose?.replace('_', ' ')}</strong></div>
              <div><span className="text-gray-500">Submitted:</span> <strong>{application.submitted_at ? new Date(application.submitted_at).toLocaleDateString() : 'N/A'}</strong></div>
            </div>
          </Card>

          {/* Decision Engine Results */}
          {decision && (
            <Card>
              <h2 className="text-lg font-semibold mb-4 flex items-center">
                <Shield size={20} className="mr-2 text-[var(--color-primary)]" />
                Decision Engine Results
              </h2>

              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                  <p className="text-3xl font-bold text-[var(--color-primary)]">{decision.credit_score || '-'}</p>
                  <p className="text-xs text-gray-500 mt-1">Credit Score</p>
                </div>
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                  <Badge variant={(riskBandColor[decision.risk_band || ''] as any) || 'default'}>
                    Band {decision.risk_band || '-'}
                  </Badge>
                  <p className="text-xs text-gray-500 mt-2">Risk Band</p>
                </div>
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                  <Badge variant={
                    decision.engine_outcome === 'auto_approve' ? 'success' :
                    decision.engine_outcome === 'auto_decline' ? 'danger' : 'warning'
                  }>
                    {decision.engine_outcome?.replace('_', ' ') || '-'}
                  </Badge>
                  <p className="text-xs text-gray-500 mt-2">Engine Outcome</p>
                </div>
              </div>

              {/* Scoring breakdown */}
              {decision.scoring_breakdown && (
                <div className="mb-4">
                  <h3 className="text-sm font-medium mb-2">Scoring Breakdown</h3>
                  <div className="space-y-2">
                    {Object.entries(decision.scoring_breakdown).map(([key, value]) => (
                      <div key={key} className="flex items-center">
                        <span className="text-xs text-gray-500 w-32 capitalize">{key.replace('_', ' ')}</span>
                        <div className="flex-1 bg-gray-100 rounded-full h-2 mx-2">
                          <div className="bg-[var(--color-primary)] h-2 rounded-full" style={{ width: `${Math.min(value, 100)}%` }} />
                        </div>
                        <span className="text-xs font-medium w-8">{value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Rules results */}
              {decision.rules_results?.rules && (
                <div>
                  <h3 className="text-sm font-medium mb-2">Rules Evaluation</h3>
                  <div className="space-y-1">
                    {decision.rules_results.rules.map((rule, i) => (
                      <div key={i} className="flex items-center text-xs py-1">
                        {rule.passed ? (
                          <CheckCircle size={14} className="text-green-500 mr-2 flex-shrink-0" />
                        ) : (
                          <XCircle size={14} className="text-red-500 mr-2 flex-shrink-0" />
                        )}
                        <span className={rule.passed ? 'text-gray-600' : 'text-red-700'}>{rule.message}</span>
                        {!rule.passed && rule.severity === 'hard' && (
                          <Badge variant="danger" className="ml-2">Hard</Badge>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          )}
        </div>

        {/* Right column - Action panel */}
        <div className="space-y-6">
          <Card>
            <h2 className="text-lg font-semibold mb-4">Underwriter Decision</h2>

            {error && <div className="mb-3 p-2 bg-red-50 text-red-700 rounded text-xs">{error}</div>}

            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Action</label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { value: 'approve', label: 'Approve', color: 'bg-green-50 border-green-300 text-green-800' },
                    { value: 'decline', label: 'Decline', color: 'bg-red-50 border-red-300 text-red-800' },
                    { value: 'refer', label: 'Refer', color: 'bg-yellow-50 border-yellow-300 text-yellow-800' },
                    { value: 'request_info', label: 'Request Info', color: 'bg-blue-50 border-blue-300 text-blue-800' },
                  ].map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => setAction(opt.value)}
                      className={`p-2 rounded-lg border text-xs font-medium transition-all
                        ${action === opt.value ? opt.color + ' ring-2 ring-offset-1' : 'border-gray-200 text-gray-500 hover:border-gray-300'}`}
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
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  />
                  <input
                    type="number"
                    placeholder="Interest Rate (%)"
                    value={approvedRate}
                    onChange={(e) => setApprovedRate(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    step="0.1"
                  />
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Reason / Notes</label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-[var(--color-primary)]"
                  placeholder="Document your decision rationale..."
                />
              </div>

              <Button
                className="w-full"
                onClick={handleDecide}
                isLoading={submitting}
                variant={action === 'decline' ? 'danger' : 'primary'}
                disabled={!action || !reason}
              >
                Confirm Decision
              </Button>
            </div>
          </Card>

          {decision?.suggested_rate && (
            <Card padding="sm">
              <h3 className="text-sm font-medium mb-2">Engine Suggestions</h3>
              <div className="text-sm space-y-1">
                <div className="flex justify-between">
                  <span className="text-gray-500">Suggested Rate:</span>
                  <span className="font-medium">{decision.suggested_rate}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Max Eligible:</span>
                  <span className="font-medium">TTD {decision.suggested_amount?.toLocaleString()}</span>
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
