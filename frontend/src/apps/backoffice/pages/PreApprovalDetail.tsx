import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, CheckCircle, XCircle, Clock, Shield, User, ShoppingBag,
  Banknote, FileText, ThumbsUp, ThumbsDown, Loader2,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import Badge from '../../../components/ui/Badge';
import { preApprovalApi } from '../../../api/endpoints';

export default function PreApprovalDetail() {
  const { ref } = useParams<{ ref: string }>();
  const [pa, setPa] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [deciding, setDeciding] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!ref) return;
    setLoading(true);
    preApprovalApi.adminDetail(ref)
      .then(res => setPa(res.data))
      .catch(() => setError('Pre-approval not found'))
      .finally(() => setLoading(false));
  }, [ref]);

  const handleDecide = async (outcome: 'pre_approved' | 'declined') => {
    if (!ref) return;
    setDeciding(true);
    try {
      await preApprovalApi.adminDecide(ref, { outcome });
      // Reload
      const res = await preApprovalApi.adminDetail(ref);
      setPa(res.data);
    } catch { setError('Decision failed'); }
    setDeciding(false);
  };

  const outcomeBadge = (outcome: string | null, status?: string) => {
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

  const fmtCurrency = (n: number | null) => n != null ? `TTD ${n.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '—';

  if (loading) return <div className="flex items-center justify-center h-40 text-[var(--color-text-muted)]"><Loader2 className="animate-spin mr-2" size={20} /> Loading...</div>;
  if (error) return <div className="text-center py-8 text-[var(--color-danger)]">{error}</div>;
  if (!pa) return <div className="text-center py-8 text-[var(--color-text-muted)]">Not found</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link to="/backoffice/pre-approvals" className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors">
          <ArrowLeft size={20} />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-[var(--color-text)]">Pre-Approval {pa.reference_code}</h1>
          <p className="text-sm text-[var(--color-text-muted)]">{pa.first_name} {pa.last_name} &middot; {new Date(pa.created_at).toLocaleString()}</p>
        </div>
        {outcomeBadge(pa.outcome, pa.status)}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Consumer Info */}
        <Card>
          <h3 className="font-semibold text-[var(--color-text)] mb-3 flex items-center"><User size={16} className="mr-2 text-[var(--color-primary)]" /> Consumer</h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div><span className="text-xs text-[var(--color-text-muted)]">Name</span><p className="text-[var(--color-text)] font-medium">{pa.first_name} {pa.last_name}</p></div>
            <div><span className="text-xs text-[var(--color-text-muted)]">Phone</span><p className="text-[var(--color-text)]">{d.phone || pa.phone || '—'}</p></div>
            {d.national_id && <div><span className="text-xs text-[var(--color-text-muted)]">National ID</span><p className="text-[var(--color-text)]">{d.national_id}</p></div>}
            {d.employment_status && <div><span className="text-xs text-[var(--color-text-muted)]">Employment</span><p className="text-[var(--color-text)] capitalize">{d.employment_status.replace(/_/g, ' ')}</p></div>}
            {d.employment_tenure && <div><span className="text-xs text-[var(--color-text-muted)]">Tenure</span><p className="text-[var(--color-text)] capitalize">{d.employment_tenure.replace(/_/g, ' ')}</p></div>}
          </div>
        </Card>

        {/* Item Info */}
        <Card>
          <h3 className="font-semibold text-[var(--color-text)] mb-3 flex items-center"><ShoppingBag size={16} className="mr-2 text-[var(--color-primary)]" /> Item</h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="col-span-2"><span className="text-xs text-[var(--color-text-muted)]">Description</span><p className="text-[var(--color-text)]">{pa.item_description || '—'}</p></div>
            <div><span className="text-xs text-[var(--color-text-muted)]">Price</span><p className="text-[var(--color-text)] font-bold">{fmtCurrency(pa.price)}</p></div>
            <div><span className="text-xs text-[var(--color-text-muted)]">Financing Amount</span><p className="text-[var(--color-text)] font-bold">{fmtCurrency(pa.financing_amount)}</p></div>
            <div><span className="text-xs text-[var(--color-text-muted)]">Merchant</span><p className="text-[var(--color-text)]">{pa.merchant_name || '—'}</p></div>
          </div>
        </Card>
      </div>

      {/* Financial Details (from referred detail if available) */}
      {d.monthly_income != null && (
        <Card>
          <h3 className="font-semibold text-[var(--color-text)] mb-3 flex items-center"><Banknote size={16} className="mr-2 text-[var(--color-primary)]" /> Financial Assessment</h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
            <div><span className="text-xs text-[var(--color-text-muted)]">Monthly Income</span><p className="text-[var(--color-text)] font-medium">{fmtCurrency(d.monthly_income)}</p></div>
            <div><span className="text-xs text-[var(--color-text-muted)]">Monthly Expenses</span><p className="text-[var(--color-text)]">{fmtCurrency(d.monthly_expenses)}</p></div>
            <div><span className="text-xs text-[var(--color-text-muted)]">Existing Loans</span><p className="text-[var(--color-text)]">{fmtCurrency(d.existing_loan_payments)}</p></div>
            <div>
              <span className="text-xs text-[var(--color-text-muted)]">DTI Ratio</span>
              <p className={`font-bold ${d.dti_ratio != null && d.dti_ratio > 0.45 ? 'text-[var(--color-danger)]' : 'text-[var(--color-success)]'}`}>
                {d.dti_ratio != null ? `${(d.dti_ratio * 100).toFixed(1)}%` : '—'}
              </p>
            </div>
            {d.ndi_amount != null && (
              <div>
                <span className="text-xs text-[var(--color-text-muted)]">Net Disposable Income</span>
                <p className={`font-bold ${d.ndi_amount < 3000 ? 'text-[var(--color-warning)]' : 'text-[var(--color-success)]'}`}>{fmtCurrency(d.ndi_amount)}</p>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Outcome Details */}
      {d.outcome_details && (
        <Card>
          <h3 className="font-semibold text-[var(--color-text)] mb-3 flex items-center"><Shield size={16} className="mr-2 text-[var(--color-primary)]" /> Decision Details</h3>
          {d.outcome_details.reasons?.length > 0 && (
            <div className="mb-3">
              <p className="text-xs font-medium text-[var(--color-text-muted)] mb-1 uppercase">Reasons</p>
              <ul className="space-y-1">
                {d.outcome_details.reasons.map((r: string, i: number) => (
                  <li key={i} className="text-sm text-[var(--color-text)] flex items-start gap-2">
                    <XCircle size={14} className="text-[var(--color-warning)] mt-0.5 shrink-0" /> {r}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {d.outcome_details.suggestions?.length > 0 && (
            <div className="mb-3">
              <p className="text-xs font-medium text-[var(--color-text-muted)] mb-1 uppercase">Suggestions</p>
              <ul className="space-y-1">
                {d.outcome_details.suggestions.map((s: string, i: number) => (
                  <li key={i} className="text-sm text-[var(--color-text-muted)]">• {s}</li>
                ))}
              </ul>
            </div>
          )}
          {d.outcome_details.admin_decision && (
            <div className="mt-3 p-3 rounded-lg bg-[var(--color-bg)] text-sm">
              <p className="text-xs font-medium text-[var(--color-text-muted)] mb-1">Admin Decision</p>
              <p className="text-[var(--color-text)]">
                Decided: <strong>{d.outcome_details.admin_decision.reason || d.outcome}</strong>
                {' '}on {new Date(d.outcome_details.admin_decision.decided_at).toLocaleString()}
              </p>
            </div>
          )}
        </Card>
      )}

      {/* Action buttons for referred cases */}
      {pa.outcome === 'referred' && pa.status === 'active' && (
        <Card>
          <h3 className="font-semibold text-[var(--color-text)] mb-3">Make a Decision</h3>
          <p className="text-sm text-[var(--color-text-muted)] mb-4">This pre-approval was referred for manual review. Review the details above and decide.</p>
          <div className="flex gap-3">
            <Button variant="outline" onClick={() => handleDecide('declined')} isLoading={deciding} disabled={deciding}>
              <ThumbsDown size={16} className="mr-2" /> Decline
            </Button>
            <Button onClick={() => handleDecide('pre_approved')} isLoading={deciding} disabled={deciding}>
              <ThumbsUp size={16} className="mr-2" /> Approve
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
