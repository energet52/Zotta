import { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  Camera, ChevronLeft, ChevronRight, Check, CheckCircle, XCircle,
  Clock, FileText, ArrowRight, Loader2, RefreshCw, Shield, AlertTriangle,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { preApprovalApi } from '../../../api/endpoints';

const STEPS = ['What Are You Buying?', 'About You', 'Consent & Verify', 'Your Result'];

const GOODS_CATEGORIES = [
  { value: 'furniture', label: 'Furniture' },
  { value: 'electronics', label: 'Electronics' },
  { value: 'appliances', label: 'Appliances' },
  { value: 'home_improvement', label: 'Home Improvement' },
  { value: 'automotive', label: 'Automotive' },
  { value: 'other', label: 'Other' },
];

const EMPLOYMENT_OPTIONS = [
  { value: 'employed_full_time', label: 'Employed full-time' },
  { value: 'employed_part_time', label: 'Employed part-time' },
  { value: 'self_employed', label: 'Self-employed / Business owner' },
  { value: 'contract', label: 'Contract / Temporary' },
  { value: 'government_employee', label: 'Government employee' },
  { value: 'retired', label: 'Retired / Pensioner' },
  { value: 'other', label: 'Other' },
];

const TENURE_OPTIONS = [
  { value: 'less_than_6_months', label: 'Less than 6 months' },
  { value: '6_to_12_months', label: '6 – 12 months' },
  { value: '1_to_2_years', label: '1 – 2 years' },
  { value: '2_to_5_years', label: '2 – 5 years' },
  { value: '5_plus_years', label: '5+ years' },
];

const INCOME_FREQUENCY = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'fortnightly', label: 'Fortnightly' },
  { value: 'annually', label: 'Annually' },
];

interface Merchant { id: number; name: string }
interface PreApprovalResult {
  reference_code: string;
  outcome: string;
  status: string;
  financing_amount: number;
  estimated_monthly_payment: number;
  estimated_tenure_months: number;
  estimated_rate: number;
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
}

export default function PreApproval() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Step 1 — Item
  const [photoMode, setPhotoMode] = useState(true);
  const [, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState('');
  const [parsing, setParsing] = useState(false);
  const [parseResult, setParseResult] = useState<any>(null);
  const [merchantSearch, setMerchantSearch] = useState('');
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [selectedMerchant, setSelectedMerchant] = useState<Merchant | null>(null);
  const [merchantManual, setMerchantManual] = useState('');
  const [itemDescription, setItemDescription] = useState('');
  const [goodsCategory, setGoodsCategory] = useState('');
  const [price, setPrice] = useState('');
  const [currency, setCurrency] = useState('TTD');
  const [hasDownpayment, setHasDownpayment] = useState(false);
  const [downpayment, setDownpayment] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Step 2 — About You
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [dob, setDob] = useState('');
  const [nationalId, setNationalId] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [monthlyIncome, setMonthlyIncome] = useState('');
  const [incomeFrequency, setIncomeFrequency] = useState('monthly');
  const [employmentStatus, setEmploymentStatus] = useState('');
  const [employmentTenure, setEmploymentTenure] = useState('');
  const [employerName, setEmployerName] = useState('');
  const [monthlyExpenses, setMonthlyExpenses] = useState('');
  const [existingLoans, setExistingLoans] = useState('');

  // Step 3 — Consent
  const [consentSoft, setConsentSoft] = useState(false);
  const [consentData, setConsentData] = useState(false);
  const [checkingEligibility, setCheckingEligibility] = useState(false);
  const [checkStage, setCheckStage] = useState(0);

  // Step 4 — Result
  const [result, setResult] = useState<PreApprovalResult | null>(null);
  const [refCode, setRefCode] = useState('');
  const [showChecklist, setShowChecklist] = useState(false);

  // Load merchants
  useEffect(() => {
    preApprovalApi.searchMerchants(merchantSearch).then(r => setMerchants(r.data || [])).catch(() => {});
  }, [merchantSearch]);

  const handlePhotoCapture = async (file: File) => {
    setPhotoFile(file);
    setPhotoPreview(URL.createObjectURL(file));
    setParsing(true);
    setError('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await preApprovalApi.parsePriceTag(fd);
      const data = res.data;
      setParseResult(data);
      if (data.error) {
        setError(data.message || 'Could not read the image. Please enter details manually.');
      } else {
        if (data.item_description) setItemDescription(data.item_description);
        if (data.price) setPrice(String(data.price));
        if (data.currency) setCurrency(data.currency);
        if (data.category_hint) setGoodsCategory(data.category_hint);
        if (data.merchant_name) setMerchantManual(data.merchant_name);
      }
    } catch {
      setError('Failed to process image. You can enter the details manually.');
    }
    setParsing(false);
  };

  const handleCheckEligibility = async () => {
    setCheckingEligibility(true);
    setCheckStage(0);
    setError('');

    const payload: Record<string, unknown> = {
      phone,
      first_name: firstName,
      last_name: lastName,
      date_of_birth: dob || undefined,
      national_id: nationalId || undefined,
      email: email || undefined,
      price: parseFloat(price),
      currency,
      downpayment: hasDownpayment ? parseFloat(downpayment || '0') : 0,
      item_description: itemDescription,
      goods_category: goodsCategory,
      merchant_id: selectedMerchant?.id || undefined,
      merchant_name_manual: selectedMerchant ? undefined : merchantManual || undefined,
      monthly_income: parseFloat(monthlyIncome),
      income_frequency: incomeFrequency,
      employment_status: employmentStatus,
      employment_tenure: employmentTenure || undefined,
      employer_name: employerName || undefined,
      monthly_expenses: parseFloat(monthlyExpenses),
      existing_loan_payments: parseFloat(existingLoans || '0'),
    };

    // Animated progress stages
    const stageTimer1 = setTimeout(() => setCheckStage(1), 1500);
    const stageTimer2 = setTimeout(() => setCheckStage(2), 4000);

    try {
      const res = await preApprovalApi.start(payload);
      setResult(res.data);
      setRefCode(res.data.reference_code);
      setStep(3);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Something went wrong. Please try again.');
    } finally {
      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);
      setCheckingEligibility(false);
    }
  };

  const handleCheckLower = async () => {
    if (!result?.alternative_amount || !refCode) return;
    setLoading(true);
    try {
      const res = await preApprovalApi.checkLowerAmount(refCode, result.alternative_amount);
      setResult(res.data);
      setRefCode(res.data.reference_code);
    } catch { setError('Failed to re-check. Please try again.'); }
    setLoading(false);
  };

  const [converting, setConverting] = useState(false);
  const handleApplyOnline = async () => {
    if (!refCode) { navigate('/apply'); return; }
    setConverting(true);
    try {
      const res = await preApprovalApi.convert(refCode);
      const appId = res.data.application_id;
      navigate(`/applications/${appId}`);
    } catch {
      // If conversion fails (e.g., not logged in), just go to apply page
      navigate('/apply');
    }
    setConverting(false);
  };

  const canProceedStep0 = parseFloat(price) > 0 && itemDescription.trim().length > 0;
  const canProceedStep1 = firstName.trim() && lastName.trim() && phone.trim() && parseFloat(monthlyIncome) > 0 && employmentStatus && parseFloat(monthlyExpenses) >= 0;
  const canProceedStep2 = consentSoft && consentData;

  const financingAmount = Math.max(0, parseFloat(price || '0') - parseFloat(downpayment || '0'));

  return (
    <div className="theme-consumer min-h-screen bg-[var(--color-bg)] text-[var(--color-text)]">
      {/* Standalone header */}
      <header className="border-b border-[var(--color-border)] bg-[var(--color-bg)]/80 backdrop-blur sticky top-0 z-30">
        <div className="max-w-lg mx-auto px-4 py-3 flex items-center justify-between">
          <Link to="/" className="text-lg font-bold text-[var(--color-primary)] tracking-tight">Zotta</Link>
          <div className="flex items-center gap-3 text-sm">
            <Link to="/pre-approval/status" className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors">Check Status</Link>
            <Link to="/login" className="text-[var(--color-primary)] hover:text-[var(--color-primary-light)] transition-colors">Sign In</Link>
          </div>
        </div>
      </header>

      <div className="max-w-lg mx-auto px-4 py-4 sm:py-6">
      {/* Progress bar */}
      {step < 3 && (
        <div className="mb-6">
          <div className="flex justify-between mb-2">
            {STEPS.map((_s, i) => (
              <div key={i} className={`text-xs font-medium ${i <= step ? 'text-[var(--color-primary)]' : 'text-[var(--color-text-muted)]'}`}>
                {i < step ? <Check size={14} className="inline" /> : null} {i + 1}
              </div>
            ))}
          </div>
          <div className="h-1.5 bg-[var(--color-surface)] rounded-full overflow-hidden">
            <div className="h-full bg-[var(--color-primary)] rounded-full transition-all duration-500" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
          </div>
          <p className="text-center text-sm text-[var(--color-text-muted)] mt-2">{STEPS[step]}</p>
        </div>
      )}

      {error && step < 3 && (
        <div className="mb-4 p-3 rounded-lg bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/30 text-sm text-[var(--color-danger)]">
          {error}
        </div>
      )}

      {/* ──────────────────── Step 0: What Are You Buying? ──────────────────── */}
      {step === 0 && (
        <Card>
          <h2 className="text-xl font-bold text-[var(--color-text)] mb-1">What are you buying?</h2>
          <p className="text-sm text-[var(--color-text-muted)] mb-5">Tell us about the item you'd like to finance</p>

          {/* Photo / Manual toggle */}
          <div className="flex gap-2 mb-4">
            <button onClick={() => setPhotoMode(true)} className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium border transition-colors ${photoMode ? 'border-[var(--color-primary)] bg-[var(--color-primary)]/10 text-[var(--color-primary)]' : 'border-[var(--color-border)] text-[var(--color-text-muted)]'}`}>
              <Camera size={16} className="inline mr-1" /> Snap Price Tag
            </button>
            <button onClick={() => setPhotoMode(false)} className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium border transition-colors ${!photoMode ? 'border-[var(--color-primary)] bg-[var(--color-primary)]/10 text-[var(--color-primary)]' : 'border-[var(--color-border)] text-[var(--color-text-muted)]'}`}>
              <FileText size={16} className="inline mr-1" /> Enter Manually
            </button>
          </div>

          {photoMode && !photoPreview && (
            <label className="block mb-4 cursor-pointer">
              <div className="border-2 border-dashed border-[var(--color-border)] rounded-xl p-8 text-center hover:border-[var(--color-primary)] transition-colors">
                <Camera size={40} className="mx-auto text-[var(--color-text-muted)] mb-3" />
                <p className="text-sm font-medium text-[var(--color-text)]">Tap to take a photo of the price tag</p>
                <p className="text-xs text-[var(--color-text-muted)] mt-1">Center the tag in frame for best results</p>
              </div>
              <input ref={fileInputRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) handlePhotoCapture(f); }} />
            </label>
          )}

          {photoPreview && (
            <div className="mb-4">
              <div className="relative rounded-lg overflow-hidden mb-2">
                <img src={photoPreview} alt="Price tag" className="w-full h-40 object-cover" />
                {parsing && (
                  <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                    <div className="text-white text-sm flex items-center"><Loader2 size={18} className="animate-spin mr-2" /> Reading your price tag...</div>
                  </div>
                )}
              </div>
              <button onClick={() => { setPhotoPreview(''); setPhotoFile(null); setParseResult(null); }} className="text-xs text-[var(--color-primary)] hover:underline">
                <RefreshCw size={12} className="inline mr-1" /> Retake photo
              </button>
              {parseResult?.confidence === 'low' && (
                <p className="text-xs text-[var(--color-warning)] mt-1"><AlertTriangle size={12} className="inline mr-1" />Some details may need correction — please verify below</p>
              )}
            </div>
          )}

          {/* Fields */}
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Store / Merchant</label>
              <div className="relative">
                <input type="text" value={selectedMerchant?.name || merchantManual || merchantSearch} onChange={e => { setMerchantSearch(e.target.value); setSelectedMerchant(null); setMerchantManual(e.target.value); }}
                  placeholder="Search for a store or type the name"
                  className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none" />
                {merchantSearch && !selectedMerchant && merchants.length > 0 && (
                  <div className="absolute z-10 w-full mt-1 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-lg max-h-40 overflow-y-auto">
                    {merchants.map(m => (
                      <button key={m.id} onClick={() => { setSelectedMerchant(m); setMerchantSearch(''); setMerchantManual(''); }}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-[var(--color-surface-hover)] text-[var(--color-text)]">
                        {m.name} <span className="text-xs text-[var(--color-success)]"><CheckCircle size={12} className="inline" /> Partner</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              {selectedMerchant && <p className="text-xs text-[var(--color-success)] mt-1"><CheckCircle size={12} className="inline" /> Approved Partner</p>}
            </div>

            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Item Description *</label>
              <input type="text" value={itemDescription} onChange={e => setItemDescription(e.target.value)}
                placeholder="e.g. Samsung 65-inch TV, 3-Piece Living Room Set"
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none" />
            </div>

            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Category</label>
              <select value={goodsCategory} onChange={e => setGoodsCategory(e.target.value)}
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none">
                <option value="">Select category</option>
                {GOODS_CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              <div className="col-span-2">
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Price *</label>
                <input type="number" value={price} onChange={e => setPrice(e.target.value)} placeholder="0.00" min="0" step="0.01"
                  className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Currency</label>
                <select value={currency} onChange={e => setCurrency(e.target.value)}
                  className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none">
                  <option value="TTD">TTD</option>
                  <option value="JMD">JMD</option>
                  <option value="BBD">BBD</option>
                  <option value="GYD">GYD</option>
                  <option value="USD">USD</option>
                </select>
              </div>
            </div>

            <div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={hasDownpayment} onChange={e => setHasDownpayment(e.target.checked)}
                  className="rounded border-[var(--color-border)] text-[var(--color-primary)] focus:ring-[var(--color-primary)]" />
                <span className="text-sm text-[var(--color-text)]">I plan to make a down payment</span>
              </label>
              {hasDownpayment && (
                <input type="number" value={downpayment} onChange={e => setDownpayment(e.target.value)} placeholder="Down payment amount" min="0" step="0.01"
                  className="w-full mt-2 px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none" />
              )}
              {hasDownpayment && (
                <p className="text-xs text-[var(--color-text-muted)] mt-1">A larger down payment can improve your chances and reduce monthly payments</p>
              )}
            </div>

            {financingAmount > 0 && (
              <div className="p-3 rounded-lg bg-[var(--color-primary)]/10 text-sm">
                <span className="text-[var(--color-text-muted)]">Amount to finance:</span>{' '}
                <span className="font-bold text-[var(--color-primary)]">{currency} {financingAmount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
              </div>
            )}
          </div>

          <div className="flex justify-end mt-5">
            <Button onClick={() => setStep(1)} disabled={!canProceedStep0}>
              Next <ChevronRight size={16} className="ml-1" />
            </Button>
          </div>
        </Card>
      )}

      {/* ──────────────────── Step 1: About You ──────────────────── */}
      {step === 1 && (
        <Card>
          <h2 className="text-xl font-bold text-[var(--color-text)] mb-1">About You</h2>
          <p className="text-sm text-[var(--color-text-muted)] mb-5">A few quick details so we can check your eligibility</p>

          <div className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">First Name *</label>
                <input type="text" value={firstName} onChange={e => setFirstName(e.target.value)} className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Last Name *</label>
                <input type="text" value={lastName} onChange={e => setLastName(e.target.value)} className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Date of Birth</label>
              <input type="date" value={dob} onChange={e => setDob(e.target.value)} className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none" />
            </div>

            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">National ID / Permit Number</label>
              <input type="text" value={nationalId} onChange={e => setNationalId(e.target.value)} placeholder="For eligibility check (soft inquiry only)"
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none" />
              <p className="text-xs text-[var(--color-text-muted)] mt-1"><Shield size={10} className="inline mr-1" />This will be a soft check that does NOT affect your credit score</p>
            </div>

            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Mobile Phone *</label>
              <input type="tel" value={phone} onChange={e => setPhone(e.target.value)} placeholder="+1 868 000 0000"
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none" />
            </div>

            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Email (optional)</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="For sending your results"
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none" />
            </div>

            <hr className="border-[var(--color-border)]" />
            <p className="text-sm font-medium text-[var(--color-text)]">Financial Information</p>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              <div className="col-span-2">
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Total Income (before tax) *</label>
                <input type="number" value={monthlyIncome} onChange={e => setMonthlyIncome(e.target.value)} placeholder="0.00" min="0"
                  className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Frequency</label>
                <select value={incomeFrequency} onChange={e => setIncomeFrequency(e.target.value)}
                  className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none">
                  {INCOME_FREQUENCY.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Employment Status *</label>
              <select value={employmentStatus} onChange={e => setEmploymentStatus(e.target.value)}
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none">
                <option value="">Select...</option>
                {EMPLOYMENT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>

            {employmentStatus && employmentStatus !== 'retired' && employmentStatus !== 'other' && (
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">
                  {employmentStatus === 'self_employed' ? 'How long has your business been operating?' : 'How long in this role?'}
                </label>
                <select value={employmentTenure} onChange={e => setEmploymentTenure(e.target.value)}
                  className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none">
                  <option value="">Select...</option>
                  {TENURE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
            )}

            {employmentStatus && !['retired', 'other', 'self_employed'].includes(employmentStatus) && (
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Employer Name (optional)</label>
                <input type="text" value={employerName} onChange={e => setEmployerName(e.target.value)}
                  className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none" />
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Monthly Living Expenses *</label>
              <input type="number" value={monthlyExpenses} onChange={e => setMonthlyExpenses(e.target.value)} placeholder="Rent, utilities, food, transport" min="0"
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none" />
            </div>

            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Monthly Loan / Credit Payments</label>
              <input type="number" value={existingLoans} onChange={e => setExistingLoans(e.target.value)} placeholder="0 if none" min="0"
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none" />
              {(!existingLoans || existingLoans === '0') && <p className="text-xs text-[var(--color-success)] mt-1">No existing payments — that helps!</p>}
            </div>
          </div>

          <div className="flex justify-between mt-5">
            <Button variant="ghost" onClick={() => setStep(0)}><ChevronLeft size={16} className="mr-1" /> Back</Button>
            <Button onClick={() => setStep(2)} disabled={!canProceedStep1}>Next <ChevronRight size={16} className="ml-1" /></Button>
          </div>
        </Card>
      )}

      {/* ──────────────────── Step 2: Consent & OTP ──────────────────── */}
      {step === 2 && !checkingEligibility && (
        <Card>
          <h2 className="text-xl font-bold text-[var(--color-text)] mb-1">Almost there</h2>
          <p className="text-sm text-[var(--color-text-muted)] mb-5">We just need your permission to check your eligibility</p>

          <div className="space-y-4">
            <label className="flex items-start gap-3 cursor-pointer p-3 rounded-lg border border-[var(--color-border)] hover:border-[var(--color-primary)] transition-colors">
              <input type="checkbox" checked={consentSoft} onChange={e => setConsentSoft(e.target.checked)}
                className="mt-0.5 rounded border-[var(--color-border)] text-[var(--color-primary)] focus:ring-[var(--color-primary)]" />
              <div>
                <p className="text-sm font-medium text-[var(--color-text)]">Soft Credit Check</p>
                <p className="text-xs text-[var(--color-text-muted)] mt-1">
                  I authorize a soft credit inquiry to assess my eligibility. A soft inquiry does <strong>NOT</strong> appear on my credit report and does <strong>NOT</strong> affect my credit score.
                </p>
              </div>
            </label>

            <label className="flex items-start gap-3 cursor-pointer p-3 rounded-lg border border-[var(--color-border)] hover:border-[var(--color-primary)] transition-colors">
              <input type="checkbox" checked={consentData} onChange={e => setConsentData(e.target.checked)}
                className="mt-0.5 rounded border-[var(--color-border)] text-[var(--color-primary)] focus:ring-[var(--color-primary)]" />
              <div>
                <p className="text-sm font-medium text-[var(--color-text)]">Personal Data Processing</p>
                <p className="text-xs text-[var(--color-text-muted)] mt-1">
                  I agree that my personal information may be processed for the purpose of assessing my eligibility for financing. My information is stored securely and not shared with third parties except as required by law.
                </p>
              </div>
            </label>
          </div>

          <div className="mt-6">
            <Button
              className="w-full py-3 text-base"
              disabled={!canProceedStep2}
              onClick={handleCheckEligibility}
              isLoading={loading}
            >
              <Shield size={18} className="mr-2" />
              Check My Eligibility
            </Button>
            <p className="text-center text-xs text-[var(--color-text-muted)] mt-2">Takes about 10 seconds</p>
          </div>

          <div className="flex justify-start mt-4">
            <Button variant="ghost" onClick={() => setStep(1)}><ChevronLeft size={16} className="mr-1" /> Back</Button>
          </div>
        </Card>
      )}

      {/* Checking animation */}
      {step === 2 && checkingEligibility && (
        <Card>
          <div className="py-12 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-3 border-[var(--color-primary)] border-t-transparent mx-auto mb-6" />
            <div className="space-y-3">
              {['Checking your information...', 'Reviewing your credit profile...', 'Calculating your eligibility...'].map((msg, i) => (
                <p key={i} className={`text-sm transition-all duration-500 ${i <= checkStage ? 'text-[var(--color-text)]' : 'text-[var(--color-text-muted)] opacity-40'}`}>
                  {i < checkStage ? <Check size={14} className="inline text-[var(--color-success)] mr-1" /> : i === checkStage ? <Loader2 size={14} className="inline animate-spin mr-1" /> : null}
                  {msg}
                </p>
              ))}
            </div>
          </div>
        </Card>
      )}

      {/* ──────────────────── Step 3: Result ──────────────────── */}
      {step === 3 && result && (
        <div className="space-y-4">
          {/* Pre-Approved */}
          {(result.outcome === 'pre_approved') && (
            <>
              <Card>
                <div className="text-center mb-4">
                  <div className="w-16 h-16 rounded-full bg-[var(--color-success)]/20 flex items-center justify-center mx-auto mb-3">
                    <CheckCircle size={32} className="text-[var(--color-success)]" />
                  </div>
                  <h2 className="text-2xl font-bold text-[var(--color-text)]">You're pre-approved!</h2>
                </div>

                <div className="rounded-lg bg-[var(--color-bg)] p-4 space-y-2 text-sm">
                  <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Item</span><span className="text-[var(--color-text)] font-medium">{result.merchant_name ? `${itemDescription} from ${result.merchant_name}` : itemDescription}</span></div>
                  <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Financing Amount</span><span className="text-[var(--color-text)] font-bold">{currency} {result.financing_amount?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>
                  <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Est. Monthly Payment</span><span className="text-[var(--color-primary)] font-bold">{currency} {result.estimated_monthly_payment?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>
                  <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Over</span><span className="text-[var(--color-text)]">{result.estimated_tenure_months} months</span></div>
                  <hr className="border-[var(--color-border)]" />
                  <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Reference</span><span className="font-mono font-bold text-[var(--color-primary)]">{result.reference_code}</span></div>
                  <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Valid Until</span><span className="text-[var(--color-text)]">{result.expires_at ? new Date(result.expires_at).toLocaleDateString() : '—'}</span></div>
                </div>

                <p className="text-xs text-[var(--color-text-muted)] mt-3 p-2 rounded bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/20">
                  This is a pre-approval based on the information you provided. Final approval is subject to document verification, income confirmation, and full assessment. Terms may change.
                </p>
              </Card>

              <div className="grid grid-cols-1 gap-3">
                <Button className="w-full py-3" onClick={handleApplyOnline} isLoading={converting}>
                  <ArrowRight size={16} className="mr-2" /> Apply Online Now
                </Button>
                <Button variant="outline" className="w-full" onClick={() => setShowChecklist(!showChecklist)}>
                  <FileText size={16} className="mr-2" /> {showChecklist ? 'Hide' : 'View'} Document Checklist
                </Button>
              </div>
            </>
          )}

          {/* Conditionally Approved */}
          {result.outcome === 'conditionally_approved' && (
            <>
              <Card>
                <div className="text-center mb-4">
                  <div className="w-16 h-16 rounded-full bg-[var(--color-warning)]/20 flex items-center justify-center mx-auto mb-3">
                    <CheckCircle size={32} className="text-[var(--color-warning)]" />
                  </div>
                  <h2 className="text-xl font-bold text-[var(--color-text)]">Pre-approved with adjustment</h2>
                </div>
                <p className="text-sm text-[var(--color-text)] mb-3">{result.message}</p>
                <div className="rounded-lg bg-[var(--color-bg)] p-4 space-y-2 text-sm">
                  <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Approved Amount</span><span className="font-bold text-[var(--color-primary)]">{currency} {(result.alternative_amount || result.financing_amount)?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>
                  <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Est. Monthly Payment</span><span className="font-bold">{currency} {(result.alternative_payment || result.estimated_monthly_payment)?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>
                  <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Reference</span><span className="font-mono font-bold text-[var(--color-primary)]">{result.reference_code}</span></div>
                </div>
                <p className="text-xs text-[var(--color-text-muted)] mt-3 p-2 rounded bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/20">
                  Pre-approval based on information provided. Final terms subject to full assessment.
                </p>
              </Card>
              <Button className="w-full py-3" onClick={handleApplyOnline} isLoading={converting}><ArrowRight size={16} className="mr-2" /> Apply Online Now</Button>
              <Button variant="outline" className="w-full" onClick={() => setShowChecklist(!showChecklist)}>
                <FileText size={16} className="mr-2" /> Document Checklist
              </Button>
            </>
          )}

          {/* Referred */}
          {result.outcome === 'referred' && (
            <Card>
              <div className="text-center mb-4">
                <div className="w-16 h-16 rounded-full bg-[var(--color-info)]/20 flex items-center justify-center mx-auto mb-3">
                  <Clock size={32} className="text-[var(--color-primary)]" />
                </div>
                <h2 className="text-xl font-bold text-[var(--color-text)]">We need a little more time</h2>
              </div>
              <p className="text-sm text-[var(--color-text)] mb-4">
                Based on what you've told us, we need to review your application more closely. <strong>This is NOT a decline</strong> — many reviewed applications are approved.
              </p>
              <div className="rounded-lg bg-[var(--color-bg)] p-4 space-y-2 text-sm mb-4">
                <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Reference</span><span className="font-mono font-bold text-[var(--color-primary)]">{result.reference_code}</span></div>
                <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Expected Timeline</span><span className="text-[var(--color-text)]">1 business day</span></div>
                <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">We'll contact you at</span><span className="text-[var(--color-text)]">{phone}</span></div>
              </div>
              <Button variant="outline" className="w-full" onClick={() => setShowChecklist(!showChecklist)}>
                <FileText size={16} className="mr-2" /> Prepare Your Documents
              </Button>
            </Card>
          )}

          {/* Declined */}
          {result.outcome === 'declined' && (
            <Card>
              <div className="text-center mb-4">
                <div className="w-16 h-16 rounded-full bg-[var(--color-danger)]/10 flex items-center justify-center mx-auto mb-3">
                  <XCircle size={32} className="text-[var(--color-danger)]" />
                </div>
                <h2 className="text-xl font-bold text-[var(--color-text)]">We can't pre-approve you right now</h2>
              </div>
              <p className="text-sm text-[var(--color-text)] mb-4">{result.message}</p>
              {result.suggestions.length > 0 && (
                <div className="rounded-lg bg-[var(--color-bg)] p-4 mb-4">
                  <p className="text-sm font-medium text-[var(--color-text)] mb-2">Here's what might help:</p>
                  <ul className="space-y-1">
                    {result.suggestions.map((s, i) => (
                      <li key={i} className="text-sm text-[var(--color-text-muted)] flex items-start gap-2">
                        <ArrowRight size={12} className="mt-1 text-[var(--color-primary)] shrink-0" /> {s}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {result.alternative_amount && (
                <Button className="w-full mb-3" onClick={handleCheckLower} isLoading={loading}>
                  Check at {currency} {result.alternative_amount.toLocaleString()} instead
                </Button>
              )}
              <Button variant="outline" className="w-full" onClick={() => navigate('/pre-approval/status')}>
                Check status later
              </Button>
            </Card>
          )}

          {/* Document checklist (shared) */}
          {showChecklist && result.document_checklist.length > 0 && (
            <Card>
              <h3 className="font-semibold text-[var(--color-text)] mb-3 flex items-center"><FileText size={16} className="mr-2" /> Documents to Prepare</h3>
              <div className="space-y-2">
                {result.document_checklist.map((doc, i) => (
                  <label key={i} className="flex items-start gap-3 p-2 rounded-lg hover:bg-[var(--color-surface-hover)] cursor-pointer">
                    <input type="checkbox" className="mt-0.5 rounded border-[var(--color-border)] text-[var(--color-primary)]" />
                    <div>
                      <p className="text-sm text-[var(--color-text)]">{doc.label}</p>
                      <p className="text-xs text-[var(--color-text-muted)]">{doc.why}</p>
                    </div>
                  </label>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}
      </div>
    </div>
  );
}
