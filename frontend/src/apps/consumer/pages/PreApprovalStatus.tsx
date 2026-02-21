import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Search, CheckCircle, XCircle, Clock, ArrowRight, RefreshCw,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { preApprovalApi } from '../../../api/endpoints';

interface StatusResult {
  reference_code: string;
  outcome: string | null;
  status: string;
  financing_amount: number | null;
  estimated_monthly_payment: number | null;
  estimated_tenure_months: number | null;
  estimated_rate: number | null;
  credit_product_name: string | null;
  expires_at: string | null;
  message: string;
  reasons: string[];
  suggestions: string[];
  alternative_amount: number | null;
  alternative_payment: number | null;
  document_checklist: { type: string; label: string; why: string }[];
  merchant_name: string | null;
  merchant_approved: boolean;
  item_description: string | null;
  price: number | null;
  currency: string;
  first_name: string | null;
  last_name: string | null;
  phone: string | null;
  created_at: string | null;
}

export default function PreApprovalStatus() {
  const { ref: urlRef } = useParams<{ ref?: string }>();
  const navigate = useNavigate();
  const [refCode, setRefCode] = useState(urlRef || '');
  const [phone, setPhone] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<StatusResult | null>(null);

  const handleLookup = async () => {
    if (!refCode || !phone) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await preApprovalApi.getStatus(refCode, phone);
      setResult(res.data);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Pre-approval not found. Please check your reference code and phone number.');
    }
    setLoading(false);
  };

  const outcomeIcon = (outcome: string | null) => {
    switch (outcome) {
      case 'pre_approved': return <CheckCircle size={40} className="text-[var(--color-success)]" />;
      case 'conditionally_approved': return <CheckCircle size={40} className="text-[var(--color-warning)]" />;
      case 'referred': return <Clock size={40} className="text-[var(--color-primary)]" />;
      case 'declined': return <XCircle size={40} className="text-[var(--color-danger)]" />;
      default: return <Clock size={40} className="text-[var(--color-text-muted)]" />;
    }
  };

  const outcomeLabel = (outcome: string | null, status: string) => {
    if (status === 'expired') return 'Expired';
    if (status === 'converted') return 'Converted to Application';
    switch (outcome) {
      case 'pre_approved': return 'Pre-Approved';
      case 'conditionally_approved': return 'Conditionally Approved';
      case 'referred': return 'Under Review';
      case 'declined': return 'Not Approved';
      default: return 'Pending';
    }
  };

  return (
    <div className="theme-consumer min-h-screen bg-[var(--color-bg)] text-[var(--color-text)]">
      {/* Standalone header */}
      <header className="border-b border-[var(--color-border)] bg-[var(--color-bg)]/80 backdrop-blur sticky top-0 z-30">
        <div className="max-w-lg mx-auto px-4 py-3 flex items-center justify-between">
          <Link to="/" className="text-lg font-bold text-[var(--color-primary)] tracking-tight">Zotta</Link>
          <div className="flex items-center gap-3 text-sm">
            <Link to="/pre-approval" className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors">Quick Check</Link>
            <Link to="/login" className="text-[var(--color-primary)] hover:text-[var(--color-primary-light)] transition-colors">Sign In</Link>
          </div>
        </div>
      </header>

      <div className="max-w-lg mx-auto px-4 py-6">
      <h1 className="text-2xl font-bold text-[var(--color-text)] mb-1">Check Your Status</h1>
      <p className="text-sm text-[var(--color-text-muted)] mb-6">Enter your reference code and phone number to view your pre-approval result</p>

      {!result && (
        <Card>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Reference Code</label>
              <input type="text" value={refCode} onChange={e => setRefCode(e.target.value.toUpperCase())} placeholder="PA-XXXXXX"
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none font-mono" />
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Phone Number</label>
              <input type="tel" value={phone} onChange={e => setPhone(e.target.value)} placeholder="The number you used"
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none" />
            </div>
            {error && (
              <p className="text-sm text-[var(--color-danger)]">{error}</p>
            )}
            <Button className="w-full" onClick={handleLookup} isLoading={loading} disabled={!refCode || !phone}>
              <Search size={16} className="mr-2" /> Look Up Status
            </Button>
          </div>

          <div className="text-center mt-4 pt-4 border-t border-[var(--color-border)]">
            <Link to="/pre-approval" className="text-sm text-[var(--color-primary)] hover:underline">
              Don't have a reference? Check your eligibility now
            </Link>
          </div>
        </Card>
      )}

      {result && (
        <div className="space-y-4">
          <Card>
            <div className="text-center mb-4">
              <div className="w-16 h-16 rounded-full bg-[var(--color-surface)] flex items-center justify-center mx-auto mb-3">
                {outcomeIcon(result.status === 'expired' ? 'expired' : result.outcome)}
              </div>
              <h2 className="text-xl font-bold text-[var(--color-text)]">{outcomeLabel(result.outcome, result.status)}</h2>
              <p className="text-xs text-[var(--color-text-muted)] mt-1">Reference: <span className="font-mono">{result.reference_code}</span></p>
            </div>

            {result.message && (
              <p className="text-sm text-[var(--color-text)] mb-3">{result.message}</p>
            )}

            <div className="rounded-lg bg-[var(--color-bg)] p-4 space-y-2 text-sm">
              {result.item_description && (
                <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Item</span><span className="text-[var(--color-text)]">{result.item_description}</span></div>
              )}
              {result.financing_amount && (
                <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Financing</span><span className="font-bold">{result.currency} {result.financing_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>
              )}
              {result.estimated_monthly_payment && (
                <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Est. Payment</span><span className="font-bold text-[var(--color-primary)]">{result.currency} {result.estimated_monthly_payment.toLocaleString(undefined, { minimumFractionDigits: 2 })}/mo</span></div>
              )}
              {result.expires_at && (
                <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Valid Until</span><span>{new Date(result.expires_at).toLocaleDateString()}</span></div>
              )}
              {result.created_at && (
                <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Checked On</span><span>{new Date(result.created_at).toLocaleDateString()}</span></div>
              )}
            </div>
          </Card>

          {/* Actions based on status */}
          {result.status === 'expired' && (
            <Button className="w-full" onClick={() => navigate('/pre-approval')}>
              <RefreshCw size={16} className="mr-2" /> Check Eligibility Again
            </Button>
          )}

          {(result.outcome === 'pre_approved' || result.outcome === 'conditionally_approved') && result.status === 'active' && (
            <Button className="w-full py-3" onClick={() => navigate('/apply')}>
              <ArrowRight size={16} className="mr-2" /> Apply Online Now
            </Button>
          )}

          {result.status === 'converted' && (
            <div className="text-center text-sm text-[var(--color-success)]">
              <CheckCircle size={16} className="inline mr-1" /> This pre-approval has been converted to a full application
            </div>
          )}

          {result.suggestions?.length > 0 && result.outcome === 'declined' && (
            <Card>
              <h3 className="font-medium text-sm text-[var(--color-text)] mb-2">What might help:</h3>
              <ul className="space-y-1">
                {result.suggestions.map((s, i) => (
                  <li key={i} className="text-sm text-[var(--color-text-muted)] flex items-start gap-2">
                    <ArrowRight size={12} className="mt-1 shrink-0 text-[var(--color-primary)]" /> {s}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Button variant="ghost" className="w-full" onClick={() => { setResult(null); setRefCode(''); setPhone(''); }}>
            Look up another reference
          </Button>
        </div>
      )}
      </div>
    </div>
  );
}
