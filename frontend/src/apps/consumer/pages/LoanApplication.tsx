import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ChevronLeft, ChevronRight, Check, Plus, Trash2, Paperclip, X,
  CreditCard, Camera, CheckCircle, Loader2,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import Combobox from '../../../components/ui/Combobox';
import SearchableSelect from '../../../components/ui/SearchableSelect';
import { OCCUPATION_OPTIONS } from '../../../constants/occupations';
import { authApi, catalogApi, loanApi } from '../../../api/endpoints';
import { useAuthStore } from '../../../store/authStore';
import HirePurchaseAgreementText from '../../../components/HirePurchaseAgreementText';
import ReferencesEditor from '../../../components/ReferencesEditor';
import type { Reference } from '../../../components/ReferencesEditor';

const STEPS = ['ID Scan', 'Personal Info', 'Employment', 'References', 'Shopping', 'Plan Selection', 'Review', 'Documents', 'Sign Contract'];

type Merchant = { id: number; name: string };
type Branch = { id: number; name: string; is_online: boolean };
type Category = { id: number; name: string };
type Product = {
  id: number;
  name: string;
  description?: string;
  min_term_months: number;
  max_term_months: number;
  min_amount: number;
  max_amount: number;
};
type CalcResult = {
  total_financed: number;
  downpayment: number;
  monthly_payment: number;
  fees_due_upfront: number;
  fees_breakdown: Array<{ fee_type: string; fee_base: string; fee_amount: number }>;
  payment_calendar: Array<{ installment_number: number; due_date: string; amount_due: number; principal: number; interest: number }>;
};

type ItemRow = {
  category_id: number | null;
  category_name: string;
  price: string;
  quantity: string;
  description: string;
};

type ScanPhase = 'start' | 'front' | 'back' | 'parsing' | 'done';

interface ParsedId {
  first_name?: string | null;
  last_name?: string | null;
  date_of_birth?: string | null;
  id_type?: string | null;
  national_id?: string | null;
  gender?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  parish?: string | null;
}

const inputClass =
  'w-full h-[38px] px-3 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50 focus:border-[var(--color-primary)]';
const selectClass =
  'w-full h-[38px] px-3 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50 focus:border-[var(--color-primary)]';

export default function LoanApplication() {
  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  // ── ID Scan state ──────────────────────────────
  const [scanPhase, setScanPhase] = useState<ScanPhase>('start');
  const [frontImage, setFrontImage] = useState<File | null>(null);
  const [backImage, setBackImage] = useState<File | null>(null);
  const [frontPreview, setFrontPreview] = useState('');
  const [backPreview, setBackPreview] = useState('');
  const [parsedFields, setParsedFields] = useState<ParsedId | null>(null);
  const [scanError, setScanError] = useState('');

  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [calculation, setCalculation] = useState<CalcResult | null>(null);

  const [merchantId, setMerchantId] = useState<number | null>(null);
  const [branchId, setBranchId] = useState<number | null>(null);
  const [items, setItems] = useState<ItemRow[]>([
    { category_id: null, category_name: '', price: '', quantity: '1', description: '' },
  ]);
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [selectedTerm, setSelectedTerm] = useState<number | null>(null);

  const [profile, setProfile] = useState({
    first_name: '', last_name: '',
    date_of_birth: '', id_type: '', national_id: '', gender: '', marital_status: '',
    address_line1: '', address_line2: '', city: '', parish: '',
    whatsapp_number: '', contact_email: '', mobile_phone: '', home_phone: '', employer_phone: '',
  });
  const [employment, setEmployment] = useState({
    employer_name: '', employer_sector: '', job_title: '', employment_type: '', years_employed: '',
    monthly_income: '', other_income: '', monthly_expenses: '', existing_debt: '', dependents: '',
  });

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

  // Document uploads (before sign)
  const DOCUMENT_TYPES = [
    { value: 'proof_of_income', label: 'Payslip' },
    { value: 'bank_statement', label: 'Bank Statement' },
    { value: 'employment_letter', label: 'Job Letter' },
    { value: 'national_id', label: 'ID Documents' },
    { value: 'utility_bill', label: 'Utility Bill' },
    { value: 'other', label: 'Other' },
  ] as const;
  type DocEntry = { id: string; documentType: string; file: File };
  const [documents, setDocuments] = useState<DocEntry[]>([]);

  // References state (stored locally until draft is created, then synced via API)
  const [localRefs, setLocalRefs] = useState<Reference[]>([]);

  // Contract signing state
  const [draftAppId, setDraftAppId] = useState<number | null>(null);
  const [draftRef, setDraftRef] = useState('');
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [hasSignature, setHasSignature] = useState(false);
  const [typedName, setTypedName] = useState('');
  const [agreed, setAgreed] = useState(false);
  const user = useAuthStore((s) => s.user);

  const totalAmount = useMemo(
    () => items.reduce((sum, it) => sum + (parseFloat(it.price || '0') * parseInt(it.quantity || '0', 10)), 0),
    [items],
  );

  const selectedProduct = products.find((p) => p.id === selectedProductId) || null;
  const termOptions = useMemo(() => {
    if (!selectedProduct) return [];
    const out: number[] = [];
    for (let t = selectedProduct.min_term_months; t <= selectedProduct.max_term_months; t += 1) {
      if (t % 3 === 0) out.push(t);
    }
    return out;
  }, [selectedProduct]);

  useEffect(() => {
    (async () => {
      try {
        const mRes = await catalogApi.getMerchants();
        setMerchants(mRes.data || []);
      } catch {
        // ignore
      }
      try {
        const pRes = await loanApi.getProfile();
        const p = pRes.data;
        setProfile((prev) => ({
          ...prev,
          date_of_birth: p.date_of_birth || '',
          id_type: p.id_type || '',
          national_id: p.national_id || '',
          gender: p.gender || '',
          marital_status: p.marital_status || '',
          address_line1: p.address_line1 || '',
          address_line2: p.address_line2 || '',
          city: p.city || '',
          parish: p.parish || '',
          whatsapp_number: p.whatsapp_number || '',
          contact_email: p.contact_email || '',
          mobile_phone: p.mobile_phone || '',
          home_phone: p.home_phone || '',
          employer_phone: p.employer_phone || '',
        }));
        setEmployment((prev) => ({
          ...prev,
          employer_name: p.employer_name || '',
          employer_sector: p.employer_sector || '',
          job_title: p.job_title || '',
          employment_type: p.employment_type || '',
          years_employed: p.years_employed != null ? String(p.years_employed) : '',
          monthly_income: p.monthly_income != null ? String(p.monthly_income) : '',
          other_income: p.other_income != null ? String(p.other_income) : '',
          monthly_expenses: p.monthly_expenses != null ? String(p.monthly_expenses) : '',
          existing_debt: p.existing_debt != null ? String(p.existing_debt) : '',
          dependents: p.dependents != null ? String(p.dependents) : '',
        }));
        // Auto-skip ID scan if user already has personal info on file
        const hasProfile = !!(p.first_name || p.national_id || p.address_line1);
        if (hasProfile) {
          setStep(1); // skip to Personal Info
        }
      } catch {
        // first-time customer
      }
    })();
  }, []);

  // Sync first/last name and email from user (auth) when available
  useEffect(() => {
    if (user) {
      setProfile((prev) => ({
        ...prev,
        first_name: user.first_name || prev.first_name,
        last_name: user.last_name || prev.last_name,
        contact_email: prev.contact_email || (user.email ?? ''),
      }));
    }
  }, [user]);

  useEffect(() => {
    if (!merchantId) {
      setBranches([]);
      setBranchId(null);
      setCategories([]);
      return;
    }
    catalogApi.getBranches(merchantId)
      .then((res) => setBranches(res.data || []))
      .catch(() => setBranches([]));
    catalogApi.getCategories(merchantId)
      .then((res) => setCategories(res.data || []))
      .catch(() => setCategories([]));
  }, [merchantId]);

  useEffect(() => {
    if (!merchantId || totalAmount <= 0) {
      setProducts([]);
      setSelectedProductId(null);
      setSelectedTerm(null);
      setCalculation(null);
      return;
    }
    catalogApi.getProducts(merchantId, totalAmount)
      .then((res) => setProducts(res.data || []))
      .catch(() => setProducts([]));
  }, [merchantId, totalAmount]);

  useEffect(() => {
    if (!selectedProductId || !selectedTerm || totalAmount <= 0) {
      setCalculation(null);
      return;
    }
    catalogApi.calculate({
      product_id: selectedProductId,
      total_amount: totalAmount,
      term_months: selectedTerm,
    }).then((res) => setCalculation(res.data)).catch(() => setCalculation(null));
  }, [selectedProductId, selectedTerm, totalAmount]);

  // ── ID Scan helpers ────────────────────────────

  const handleImageCapture = (file: File, side: 'front' | 'back') => {
    const url = URL.createObjectURL(file);
    if (side === 'front') {
      setFrontImage(file);
      setFrontPreview(url);
    } else {
      setBackImage(file);
      setBackPreview(url);
    }
  };

  const handleParseId = async () => {
    if (!frontImage || !backImage) return;
    setScanPhase('parsing');
    setScanError('');
    try {
      const formData = new FormData();
      formData.append('front_image', frontImage);
      formData.append('back_image', backImage);
      const res = await loanApi.parseId(formData);
      const parsed: ParsedId = res.data;
      setParsedFields(parsed);

      setProfile((prev) => ({
        ...prev,
        first_name: parsed.first_name || prev.first_name,
        last_name: parsed.last_name || prev.last_name,
        date_of_birth: parsed.date_of_birth || prev.date_of_birth,
        id_type: parsed.id_type || prev.id_type,
        national_id: parsed.national_id || prev.national_id,
        gender: parsed.gender || prev.gender,
        address_line1: parsed.address_line1 || prev.address_line1,
        address_line2: parsed.address_line2 || prev.address_line2,
        city: parsed.city || prev.city,
        parish: parsed.parish || prev.parish,
      }));

      setScanPhase('done');
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setScanError(typeof detail === 'string' ? detail : 'Failed to parse ID. You can skip and enter details manually.');
      setScanPhase('back');
    }
  };

  // ── Handlers ───────────────────────────────────

  const emptyToUndef = (v: string) => (v === '' ? undefined : v);

  /** Create draft application and profile, then move to Documents step. */
  const handleCreateDraft = async () => {
    if (!merchantId || !branchId || !selectedProductId || !selectedTerm) {
      setError('Please complete shopping and product selection before submitting.');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      if (profile.first_name || profile.last_name) {
        await authApi.updateMe({
          first_name: profile.first_name || undefined,
          last_name: profile.last_name || undefined,
        });
      }
      await loanApi.updateProfile({
        date_of_birth: emptyToUndef(profile.date_of_birth),
        id_type: emptyToUndef(profile.id_type),
        national_id: emptyToUndef(profile.national_id),
        gender: emptyToUndef(profile.gender),
        marital_status: emptyToUndef(profile.marital_status),
        address_line1: emptyToUndef(profile.address_line1),
        address_line2: emptyToUndef(profile.address_line2),
        city: emptyToUndef(profile.city),
        parish: emptyToUndef(profile.parish),
        whatsapp_number: emptyToUndef(profile.whatsapp_number),
        contact_email: emptyToUndef(profile.contact_email),
        mobile_phone: emptyToUndef(profile.mobile_phone),
        home_phone: emptyToUndef(profile.home_phone),
        employer_phone: emptyToUndef(profile.employer_phone),
        years_employed: employment.years_employed ? parseInt(employment.years_employed, 10) : undefined,
        monthly_income: employment.monthly_income ? parseFloat(employment.monthly_income) : undefined,
        other_income: employment.other_income ? parseFloat(employment.other_income) : undefined,
        monthly_expenses: employment.monthly_expenses ? parseFloat(employment.monthly_expenses) : undefined,
        existing_debt: employment.existing_debt ? parseFloat(employment.existing_debt) : undefined,
        dependents: employment.dependents ? parseInt(employment.dependents, 10) : undefined,
        employer_name: emptyToUndef(employment.employer_name),
        employer_sector: emptyToUndef(employment.employer_sector),
        job_title: emptyToUndef(employment.job_title),
        employment_type: emptyToUndef(employment.employment_type),
      });

      const res = await loanApi.create({
        amount_requested: totalAmount,
        term_months: selectedTerm,
        purpose: 'personal',
        purpose_description: `Hire purchase at merchant ${merchantId}, branch ${branchId}`,
        merchant_id: merchantId,
        branch_id: branchId,
        credit_product_id: selectedProductId,
        downpayment: calculation?.downpayment || 0,
        total_financed: calculation?.total_financed || totalAmount,
        items: items
          .filter((it) => it.category_id && parseFloat(it.price || '0') > 0 && parseInt(it.quantity || '0', 10) > 0)
          .map((it) => ({
            category_id: it.category_id as number,
            description: it.description || undefined,
            price: parseFloat(it.price),
            quantity: parseInt(it.quantity, 10),
          })),
      });
      const appId = res.data.id;
      setDraftAppId(appId);
      setDraftRef(res.data.reference_number);

      // Save references to the new application
      for (const ref of localRefs) {
        try {
          await loanApi.addReference(appId, {
            name: ref.name,
            relationship_type: ref.relationship_type,
            phone: ref.phone,
            address: ref.address,
            directions: ref.directions || undefined,
          });
        } catch { /* continue saving other refs */ }
      }

      setStep(7); // Documents step
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') setError(detail);
      else if (Array.isArray(detail)) setError(detail.map((e: any) => e.msg || String(e)).join('; '));
      else setError('Failed to create application');
    } finally {
      setSubmitting(false);
    }
  };

  /** Upload documents and proceed to Sign step. */
  const handleContinueFromDocuments = async () => {
    if (!draftAppId) return;
    setSubmitting(true);
    setError('');
    try {
      for (const doc of documents) {
        const formData = new FormData();
        formData.append('document_type', doc.documentType);
        formData.append('file', doc.file);
        await loanApi.uploadDocument(draftAppId, formData);
      }
      setStep(8); // Sign Contract step
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (typeof detail === 'string') setError(detail);
      else if (Array.isArray(detail)) setError(detail.map((e: any) => e.msg || String(e)).join('; '));
      else setError('Failed to upload documents');
    } finally {
      setSubmitting(false);
    }
  };

  /** Sign consent and submit the draft application. */
  const handleSignAndSubmit = async () => {
    if (!draftAppId || !hasSignature || !typedName || !agreed) return;
    setSubmitting(true);
    setError('');
    try {
      const canvas = canvasRef.current;
      const signatureData = canvas?.toDataURL('image/png') || '';
      await loanApi.submitWithConsent(draftAppId, {
        signature_data: signatureData,
        typed_name: typedName,
        agreed: true,
      });
      navigate(`/applications/${draftAppId}`);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') setError(detail);
      else if (Array.isArray(detail)) setError(detail.map((e: any) => e.msg || String(e)).join('; '));
      else setError('Failed to submit application');
    } finally {
      setSubmitting(false);
    }
  };

  // ── Signature canvas helpers ───────────────────────
  const initCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * 2;
    canvas.height = rect.height * 2;
    ctx.scale(2, 2);
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#e2e8f0'; // light stroke on dark bg
    ctx.lineWidth = 2;
  }, []);

  useEffect(() => { if (step === 8) setTimeout(initCanvas, 100); }, [step, initCanvas]);

  const getCoords = (e: React.MouseEvent | React.TouchEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    if ('touches' in e) return { x: e.touches[0].clientX - rect.left, y: e.touches[0].clientY - rect.top };
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };
  const startDraw = (e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    const ctx = canvasRef.current?.getContext('2d');
    if (!ctx) return;
    setIsDrawing(true);
    const { x, y } = getCoords(e);
    ctx.beginPath();
    ctx.moveTo(x, y);
  };
  const draw = (e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    if (!isDrawing) return;
    const ctx = canvasRef.current?.getContext('2d');
    if (!ctx) return;
    const { x, y } = getCoords(e);
    ctx.lineTo(x, y);
    ctx.stroke();
    setHasSignature(true);
  };
  const stopDraw = () => setIsDrawing(false);
  const clearSig = () => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (canvas && ctx) { ctx.clearRect(0, 0, canvas.width, canvas.height); setHasSignature(false); }
  };

  const applicantFullName = [profile.first_name, profile.last_name].filter(Boolean).join(' ')
    || (user ? `${user.first_name} ${user.last_name}`.trim() : '');
  const applicantAddress = [profile.address_line1, profile.address_line2, profile.city, profile.parish].filter(Boolean).join(', ') || 'Not provided';

  // ── Step gating ────────────────────────────────
  // Steps: 0=ID Scan, 1=Personal Info, 2=Employment, 3=Shopping, 4=Plan Selection, 5=Review, 6=Documents, 7=Sign Contract

  const canProceed = () => {
    if (step === 0) return scanPhase === 'done' || scanPhase === 'start';
    if (step === 4) return merchantId && branchId && totalAmount > 0;
    if (step === 5) return selectedProductId && selectedTerm && calculation;
    return true;
  };

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-[var(--color-text)]">Hire-Purchase Application</h1>
      <div className="flex items-center mb-8 overflow-x-auto max-w-full">
        {STEPS.map((label, i) => (
          <div key={label} className="flex items-center flex-1 min-w-0">
            <div className="flex items-center">
              <div className={`w-8 h-8 shrink-0 rounded-full flex items-center justify-center text-sm font-medium ${i < step ? 'bg-[var(--color-success)] text-white' : i === step ? 'bg-[var(--color-primary)] text-white' : 'bg-[var(--color-border)] text-[var(--color-text-muted)]'}`}>
                {i < step ? <Check size={16} /> : i + 1}
              </div>
              <span className={`ml-2 text-sm hidden sm:inline whitespace-nowrap ${i === step ? 'font-medium text-[var(--color-text)]' : 'text-[var(--color-text-muted)]'}`}>{label}</span>
            </div>
            {i < STEPS.length - 1 && <div className="flex-1 h-px bg-[var(--color-border)] mx-3" />}
          </div>
        ))}
      </div>

      {error && <div className="mb-4 p-3 bg-red-500/20 text-red-400 rounded-lg text-sm border border-red-500/30">{error}</div>}

      <Card padding="lg">
        {/* ── Step 0: ID Scan ───────────────────────── */}
        {step === 0 && (
          <div className="space-y-6">
            {scanPhase === 'start' && (
              <div className="flex flex-col items-center justify-center py-12 space-y-6">
                <div className="p-4 sm:p-6 bg-[var(--color-primary)]/10 rounded-full">
                  <CreditCard className="text-[var(--color-primary)]" size={48} />
                </div>
                <div className="text-center space-y-2">
                  <h2 className="text-xl font-bold text-[var(--color-text)]">Scan Your ID</h2>
                  <p className="text-sm text-[var(--color-text-muted)] max-w-sm">
                    Take photos of the front and back of your national ID to automatically fill in your details.
                  </p>
                </div>
                <Button onClick={() => setScanPhase('front')} className="min-h-[48px] px-8 text-base">
                  <Camera size={20} className="mr-2" /> Start ID Scan
                </Button>
                <button onClick={() => setStep(1)} className="text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] underline">
                  Skip ID Scan
                </button>
              </div>
            )}

            {scanPhase === 'front' && (
              <div className="flex flex-col items-center space-y-6">
                <div className="text-center space-y-2">
                  <h2 className="text-lg font-semibold text-[var(--color-text)]">Front of ID</h2>
                  <p className="text-sm text-[var(--color-text-muted)]">Take a clear photo of the <strong>front side</strong> of your ID card.</p>
                </div>
                {frontPreview ? (
                  <div className="space-y-4 w-full max-w-sm">
                    <img src={frontPreview} alt="Front of ID" className="w-full rounded-lg border border-[var(--color-border)] object-cover max-h-56" />
                    <div className="flex gap-3">
                      <Button variant="outline" className="flex-1 min-h-[48px]" onClick={() => { setFrontImage(null); setFrontPreview(''); }}>Retake</Button>
                      <Button className="flex-1 min-h-[48px]" onClick={() => setScanPhase('back')}>Continue <ChevronRight size={16} className="ml-1" /></Button>
                    </div>
                  </div>
                ) : (
                  <label className="flex flex-col items-center justify-center w-full max-w-sm h-56 border-2 border-dashed border-[var(--color-border)] rounded-xl cursor-pointer hover:border-[var(--color-primary)] transition-colors bg-[var(--color-surface)]">
                    <Camera size={36} className="text-[var(--color-text-muted)] mb-3" />
                    <span className="text-sm font-medium text-[var(--color-text)]">Tap to take photo</span>
                    <span className="text-xs text-[var(--color-text-muted)] mt-1">or select from gallery</span>
                    <input type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => { const file = e.target.files?.[0]; if (file) handleImageCapture(file, 'front'); e.target.value = ''; }} />
                  </label>
                )}
                <button onClick={() => setStep(1)} className="text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] underline">Skip ID Scan</button>
              </div>
            )}

            {scanPhase === 'back' && (
              <div className="flex flex-col items-center space-y-6">
                <div className="text-center space-y-2">
                  <h2 className="text-lg font-semibold text-[var(--color-text)]">Back of ID</h2>
                  <p className="text-sm text-[var(--color-text-muted)]">Now take a clear photo of the <strong>back side</strong> of your ID card.</p>
                </div>
                {scanError && <div className="w-full max-w-sm p-3 bg-red-500/20 text-red-400 rounded-lg text-sm border border-red-500/30">{scanError}</div>}
                {backPreview ? (
                  <div className="space-y-4 w-full max-w-sm">
                    <img src={backPreview} alt="Back of ID" className="w-full rounded-lg border border-[var(--color-border)] object-cover max-h-56" />
                    <div className="flex gap-3">
                      <Button variant="outline" className="flex-1 min-h-[48px]" onClick={() => { setBackImage(null); setBackPreview(''); }}>Retake</Button>
                      <Button className="flex-1 min-h-[48px]" onClick={handleParseId}>Scan & Read ID <CheckCircle size={16} className="ml-1" /></Button>
                    </div>
                  </div>
                ) : (
                  <label className="flex flex-col items-center justify-center w-full max-w-sm h-56 border-2 border-dashed border-[var(--color-border)] rounded-xl cursor-pointer hover:border-[var(--color-primary)] transition-colors bg-[var(--color-surface)]">
                    <Camera size={36} className="text-[var(--color-text-muted)] mb-3" />
                    <span className="text-sm font-medium text-[var(--color-text)]">Tap to take photo</span>
                    <span className="text-xs text-[var(--color-text-muted)] mt-1">or select from gallery</span>
                    <input type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => { const file = e.target.files?.[0]; if (file) handleImageCapture(file, 'back'); e.target.value = ''; }} />
                  </label>
                )}
                <div className="flex gap-4">
                  <button onClick={() => setScanPhase('front')} className="text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] underline">Back to front</button>
                  <button onClick={() => setStep(1)} className="text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] underline">Skip ID Scan</button>
                </div>
              </div>
            )}

            {scanPhase === 'parsing' && (
              <div className="flex flex-col items-center justify-center py-16 space-y-4">
                <Loader2 size={40} className="text-[var(--color-primary)] animate-spin" />
                <p className="text-lg font-medium text-[var(--color-text)]">Reading ID...</p>
                <p className="text-sm text-[var(--color-text-muted)]">Extracting your details from the ID photos</p>
              </div>
            )}

            {scanPhase === 'done' && (
              <div className="flex flex-col items-center space-y-6 py-8">
                <div className="p-4 bg-emerald-500/10 rounded-full"><CheckCircle className="text-emerald-400" size={40} /></div>
                <div className="text-center space-y-1">
                  <h2 className="text-lg font-semibold text-[var(--color-text)]">ID Scanned Successfully</h2>
                  <p className="text-sm text-[var(--color-text-muted)]">The following details have been pre-filled</p>
                </div>
                {parsedFields && (
                  <div className="w-full max-w-md bg-[var(--color-bg)] rounded-lg p-4 space-y-2 text-sm">
                    {parsedFields.first_name && <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Name</span><span className="font-medium text-[var(--color-text)]">{parsedFields.first_name} {parsedFields.last_name}</span></div>}
                    {parsedFields.national_id && <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">{parsedFields.id_type === 'drivers_license' ? 'Driver\'s License' : parsedFields.id_type === 'passport' ? 'Passport' : parsedFields.id_type === 'tax_number' ? 'Tax Number' : 'National ID'}</span><span className="font-medium text-[var(--color-text)]">{parsedFields.national_id}</span></div>}
                    {parsedFields.date_of_birth && <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Date of Birth</span><span className="font-medium text-[var(--color-text)]">{parsedFields.date_of_birth}</span></div>}
                    {parsedFields.gender && <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Gender</span><span className="font-medium text-[var(--color-text)] capitalize">{parsedFields.gender}</span></div>}
                    {parsedFields.address_line1 && <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Address</span><span className="font-medium text-[var(--color-text)] text-right max-w-[60%]">{[parsedFields.address_line1, parsedFields.city, parsedFields.parish].filter(Boolean).join(', ')}</span></div>}
                  </div>
                )}
                <p className="text-xs text-[var(--color-text-muted)]">You can edit these details in the next step</p>
              </div>
            )}
          </div>
        )}

        {/* ── Step 1: Personal Information ──────────── */}
        {step === 1 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-[var(--color-text)]">Personal Information</h2>
            {parsedFields && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-sm text-emerald-400 flex items-center gap-2">
                <CheckCircle size={16} /> Fields pre-filled from ID scan. Please review and correct if needed.
              </div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">First Name</label>
                <input value={profile.first_name} onChange={(e) => setProfile({ ...profile, first_name: e.target.value })} placeholder="First name" className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Last Name</label>
                <input value={profile.last_name} onChange={(e) => setProfile({ ...profile, last_name: e.target.value })} placeholder="Last name" className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Date of Birth</label>
                <input type="date" value={profile.date_of_birth} onChange={(e) => setProfile({ ...profile, date_of_birth: e.target.value })} className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">ID Type</label>
                <select value={profile.id_type} onChange={(e) => setProfile({ ...profile, id_type: e.target.value })} className={selectClass}>
                  <option value="">Select ID type</option>
                  <option value="national_id">National ID</option>
                  <option value="passport">Passport</option>
                  <option value="drivers_license">Driver&apos;s License</option>
                  <option value="tax_number">Tax Number</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">ID Number</label>
                <input value={profile.national_id} onChange={(e) => setProfile({ ...profile, national_id: e.target.value })} placeholder="Enter ID number" className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Gender</label>
                <select value={profile.gender} onChange={(e) => setProfile({ ...profile, gender: e.target.value })} className={selectClass}>
                  <option value="">Select gender</option><option value="male">Male</option><option value="female">Female</option><option value="other">Other</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Marital Status</label>
                <select value={profile.marital_status} onChange={(e) => setProfile({ ...profile, marital_status: e.target.value })} className={selectClass}>
                  <option value="">Select status</option><option value="single">Single</option><option value="married">Married</option><option value="divorced">Divorced</option><option value="widowed">Widowed</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Address Line 1</label>
              <input value={profile.address_line1} onChange={(e) => setProfile({ ...profile, address_line1: e.target.value })} placeholder="Address line 1" className={inputClass} />
            </div>
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Address Line 2 (optional)</label>
              <input value={profile.address_line2} onChange={(e) => setProfile({ ...profile, address_line2: e.target.value })} placeholder="Address line 2 (optional)" className={inputClass} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">City</label>
                <input value={profile.city} onChange={(e) => setProfile({ ...profile, city: e.target.value })} placeholder="City" className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Parish</label>
                <input value={profile.parish} onChange={(e) => setProfile({ ...profile, parish: e.target.value })} placeholder="Parish" className={inputClass} />
              </div>
            </div>

            <h3 className="font-medium text-[var(--color-text)] pt-4 border-t border-[var(--color-border)] mt-6">Contact Details</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">WhatsApp Number</label>
                <input value={profile.whatsapp_number} onChange={(e) => setProfile({ ...profile, whatsapp_number: e.target.value })} placeholder="e.g. +1 868 123 4567" className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Email</label>
                <input type="email" value={profile.contact_email} onChange={(e) => setProfile({ ...profile, contact_email: e.target.value })} placeholder="Contact email" className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Mobile Phone</label>
                <input value={profile.mobile_phone} onChange={(e) => setProfile({ ...profile, mobile_phone: e.target.value })} placeholder="Mobile phone" className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Home Phone</label>
                <input value={profile.home_phone} onChange={(e) => setProfile({ ...profile, home_phone: e.target.value })} placeholder="Home phone" className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Employer&apos;s Phone</label>
                <input value={profile.employer_phone} onChange={(e) => setProfile({ ...profile, employer_phone: e.target.value })} placeholder="Employer phone" className={inputClass} />
              </div>
            </div>
          </div>
        )}

        {/* ── Step 2: Employment & Income ───────────── */}
        {step === 2 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-[var(--color-text)]">Employment & Income</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Employer Name</label>
                <input value={employment.employer_name} onChange={(e) => setEmployment({ ...employment, employer_name: e.target.value })} placeholder="Employer name" className={inputClass} />
              </div>
              <SearchableSelect
                label="Employment Sector"
                labelClassName="block text-xs text-[var(--color-text-muted)] mb-1"
                value={employment.employer_sector}
                onChange={(v) => setEmployment({ ...employment, employer_sector: v })}
                options={EMPLOYER_SECTORS.map((s) => ({ value: s, label: s }))}
                placeholder="Search or select sector..."
              />
              <SearchableSelect
                label="Occupation / Job Title"
                labelClassName="block text-xs text-[var(--color-text-muted)] mb-1"
                value={employment.job_title}
                onChange={(v) => setEmployment({ ...employment, job_title: v })}
                options={OCCUPATION_OPTIONS.map((s) => ({ value: s, label: s }))}
                placeholder="Search or select occupation..."
                allowOther
                otherPlaceholder="Enter your occupation..."
              />
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Employment Type</label>
                <select value={employment.employment_type} onChange={(e) => setEmployment({ ...employment, employment_type: e.target.value })} className={selectClass}>
                  <option value="">Select type</option><option value="employed">Employed</option><option value="self_employed">Self-Employed</option><option value="contract">Contract</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Years Employed</label>
                <input type="number" value={employment.years_employed} onChange={(e) => setEmployment({ ...employment, years_employed: e.target.value })} placeholder="Years employed" className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Monthly Income</label>
                <input type="number" value={employment.monthly_income} onChange={(e) => setEmployment({ ...employment, monthly_income: e.target.value })} placeholder="Monthly income" className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Other Income</label>
                <input type="number" value={employment.other_income} onChange={(e) => setEmployment({ ...employment, other_income: e.target.value })} placeholder="Other income" className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Monthly Expenses</label>
                <input type="number" value={employment.monthly_expenses} onChange={(e) => setEmployment({ ...employment, monthly_expenses: e.target.value })} placeholder="Monthly expenses" className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Existing Debt</label>
                <input type="number" value={employment.existing_debt} onChange={(e) => setEmployment({ ...employment, existing_debt: e.target.value })} placeholder="Existing debt" className={inputClass} />
              </div>
            </div>
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Number of Dependents</label>
              <input type="number" value={employment.dependents} onChange={(e) => setEmployment({ ...employment, dependents: e.target.value })} placeholder="Number of dependents" className={inputClass} />
            </div>
          </div>
        )}

        {/* ── Step 3: References ────────────────────── */}
        {step === 3 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-[var(--color-text)]">References</h2>
            <p className="text-sm text-[var(--color-text-muted)]">
              Add at least one person who can vouch for your address and employment.
              You can also include directions to your house for goods delivery.
            </p>
            <ReferencesEditor
              references={localRefs}
              onAdd={async (ref) => {
                setLocalRefs((prev) => [...prev, { ...ref, id: Date.now() }]);
              }}
              onUpdate={async (id, ref) => {
                setLocalRefs((prev) => prev.map((r) => r.id === id ? { ...r, ...ref } : r));
              }}
              onDelete={async (id) => {
                setLocalRefs((prev) => prev.filter((r) => r.id !== id));
              }}
            />
          </div>
        )}

        {/* ── Step 4: Shopping Context (was step 3) ── */}
        {step === 4 && (
          <div className="space-y-5">
            <h2 className="text-lg font-semibold text-[var(--color-text)]">Shopping Context</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Combobox
                label="Merchant"
                value={merchantId}
                options={merchants}
                placeholder="Search merchant..."
                onChange={(id) => setMerchantId(id)}
              />
              <Combobox
                label="Branch"
                value={branchId}
                options={branches}
                placeholder="Search branch..."
                onChange={(id) => setBranchId(id)}
                formatOption={(b) => `${b.name}${b.is_online ? ' (Online)' : ''}`}
              />
            </div>

            <h3 className="font-medium text-[var(--color-text)]">Items for Installments</h3>
            <div className="space-y-3">
              {items.map((item, idx) => (
                <div key={idx} className="grid grid-cols-1 md:grid-cols-6 gap-2 items-end border border-[var(--color-border)] rounded-lg p-3 bg-[var(--color-surface)]">
                  <div className="md:col-span-2">
                    <Combobox
                      label="Category"
                      value={item.category_id}
                      options={categories}
                      placeholder="Search category..."
                      onChange={(id, label) => setItems((prev) => prev.map((it, i) => i === idx ? { ...it, category_id: id, category_name: label } : it))}
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-[var(--color-text-muted)] mb-1">Price</label>
                    <input
                      type="number"
                      value={item.price}
                      onChange={(e) => setItems((prev) => prev.map((it, i) => i === idx ? { ...it, price: e.target.value } : it))}
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-[var(--color-text-muted)] mb-1">Qty</label>
                    <input
                      type="number"
                      min={1}
                      value={item.quantity}
                      onChange={(e) => setItems((prev) => prev.map((it, i) => i === idx ? { ...it, quantity: e.target.value } : it))}
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-[var(--color-text-muted)] mb-1">Description</label>
                    <input
                      value={item.description}
                      onChange={(e) => setItems((prev) => prev.map((it, i) => i === idx ? { ...it, description: e.target.value } : it))}
                      className={inputClass}
                    />
                  </div>
                  <div className="flex justify-end">
                    <button
                      className="text-[var(--color-danger)] hover:text-red-400"
                      onClick={() => setItems((prev) => prev.length === 1 ? prev : prev.filter((_, i) => i !== idx))}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
            <Button variant="outline" onClick={() => setItems((prev) => [...prev, { category_id: null, category_name: '', price: '', quantity: '1', description: '' }])}>
              <Plus size={14} className="mr-1" /> Add Item
            </Button>
            <div className="text-right">
              <p className="text-sm text-[var(--color-text-muted)]">Total Purchase Amount</p>
              <p className="text-2xl font-bold text-[var(--color-text)]">TTD {totalAmount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
            </div>
          </div>
        )}

        {/* ── Step 4: Plan Selection ────────────────── */}
        {step === 5 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-[var(--color-text)]">Select Credit Product & Tenure</h2>
            {products.length === 0 ? (
              <p className="text-sm text-[var(--color-text-muted)]">No eligible products for current merchant and amount.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {products.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => {
                      setSelectedProductId(p.id);
                      setSelectedTerm(null);
                    }}
                    className={`text-left border rounded-lg p-4 transition-colors ${selectedProductId === p.id ? 'border-[var(--color-primary)] ring-2 ring-[var(--color-primary)]/20 bg-[var(--color-surface-hover)]' : 'border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]'}`}
                  >
                    <p className="font-semibold text-[var(--color-text)]">{p.name}</p>
                    <p className="text-sm text-[var(--color-text-muted)]">{p.description || 'No description'}</p>
                    <p className="text-xs text-[var(--color-text-muted)] mt-2">
                      Term {p.min_term_months}-{p.max_term_months} months &bull; Amount {p.min_amount.toLocaleString()} - {p.max_amount.toLocaleString()}
                    </p>
                  </button>
                ))}
              </div>
            )}
            {selectedProduct && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label className="block text-xs text-[var(--color-text-muted)] mb-1">Tenure</label>
                  <select
                    value={selectedTerm ?? ''}
                    onChange={(e) => setSelectedTerm(e.target.value ? Number(e.target.value) : null)}
                    className={inputClass}
                  >
                    <option value="">Select tenure</option>
                    {termOptions.map((t) => <option key={t} value={t}>{t} months</option>)}
                  </select>
                </div>
              </div>
            )}
            {calculation && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="p-3 bg-[var(--color-bg)] rounded-lg"><p className="text-xs text-[var(--color-text-muted)]">Total Financed</p><p className="font-bold text-[var(--color-text)]">TTD {calculation.total_financed.toLocaleString()}</p></div>
                  <div className="p-3 bg-[var(--color-bg)] rounded-lg"><p className="text-xs text-[var(--color-text-muted)]">Downpayment</p><p className="font-bold text-[var(--color-text)]">TTD {calculation.downpayment.toLocaleString()}</p></div>
                  <div className="p-3 bg-[var(--color-bg)] rounded-lg"><p className="text-xs text-[var(--color-text-muted)]">Fees Upfront</p><p className="font-bold text-[var(--color-text)]">TTD {calculation.fees_due_upfront.toLocaleString()}</p></div>
                  <div className="p-3 bg-[var(--color-primary)]/10 rounded-lg"><p className="text-xs text-[var(--color-primary)]">Monthly Payment</p><p className="font-bold text-[var(--color-primary)]">TTD {calculation.monthly_payment.toLocaleString()}</p></div>
                </div>
                <div>
                  <h3 className="font-medium mb-2 text-[var(--color-text)]">Payment Calendar</h3>
                  <div className="border border-[var(--color-border)] rounded-lg overflow-auto max-h-72">
                    <table className="w-full text-sm">
                      <thead><tr className="bg-[var(--color-surface-hover)]"><th className="px-3 py-2 text-left text-[var(--color-text-muted)]">#</th><th className="px-3 py-2 text-left text-[var(--color-text-muted)]">Due Date</th><th className="px-3 py-2 text-left text-[var(--color-text-muted)]">Principal</th><th className="px-3 py-2 text-left text-[var(--color-text-muted)]">Interest</th><th className="px-3 py-2 text-left text-[var(--color-text-muted)]">Amount Due</th></tr></thead>
                      <tbody>
                        {calculation.payment_calendar.map((row) => (
                          <tr key={row.installment_number} className="border-t border-[var(--color-border)]">
                            <td className="px-3 py-2 text-[var(--color-text)]">{row.installment_number}</td>
                            <td className="px-3 py-2 text-[var(--color-text)]">{new Date(row.due_date).toLocaleDateString()}</td>
                            <td className="px-3 py-2 text-[var(--color-text)]">TTD {row.principal.toLocaleString()}</td>
                            <td className="px-3 py-2 text-[var(--color-text)]">TTD {row.interest.toLocaleString()}</td>
                            <td className="px-3 py-2 font-medium text-[var(--color-text)]">TTD {row.amount_due.toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Step 5: Review ────────────────────────── */}
        {step === 6 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-[var(--color-text)]">Review & Submit</h2>

            {/* Select Credit Product & Tenure - shown on review screen */}
            <div>
              <h3 className="font-medium mb-3 text-[var(--color-text)]">Select Credit Product & Tenure</h3>
              <div className="bg-[var(--color-bg)] rounded-lg p-4 space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div><p className="text-xs text-[var(--color-text-muted)] mb-1">Product</p><p className="font-semibold text-[var(--color-text)]">{selectedProduct?.name || '—'}</p></div>
                  <div><p className="text-xs text-[var(--color-text-muted)] mb-1">Tenure</p><p className="font-semibold text-[var(--color-text)]">{selectedTerm || '—'} months</p></div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 pt-2 border-t border-[var(--color-border)]">
                  <div><p className="text-xs text-[var(--color-text-muted)]">Total Financed</p><p className="font-bold text-[var(--color-text)]">TTD {(calculation?.total_financed || totalAmount).toLocaleString()}</p></div>
                  <div><p className="text-xs text-[var(--color-text-muted)]">Downpayment</p><p className="font-bold text-[var(--color-text)]">TTD {(calculation?.downpayment || 0).toLocaleString()}</p></div>
                  <div><p className="text-xs text-[var(--color-text-muted)]">Fees Upfront</p><p className="font-bold text-[var(--color-text)]">TTD {(calculation?.fees_due_upfront || 0).toLocaleString()}</p></div>
                  <div><p className="text-xs text-[var(--color-primary)]">Monthly Payment</p><p className="font-bold text-[var(--color-primary)]">TTD {(calculation?.monthly_payment || 0).toLocaleString()}</p></div>
                </div>
              </div>
            </div>

            <div>
              <h3 className="font-medium mb-3 text-[var(--color-text)]">Shopping Context</h3>
              <div className="bg-[var(--color-bg)] rounded-lg p-4 space-y-2 text-sm">
                <p><span className="text-[var(--color-text-muted)]">Merchant:</span> <span className="text-[var(--color-text)]">{merchants.find((m) => m.id === merchantId)?.name || '—'}</span></p>
                <p><span className="text-[var(--color-text-muted)]">Branch:</span> <span className="text-[var(--color-text)]">{branches.find((b) => b.id === branchId)?.name || '—'}</span></p>
                <p><span className="text-[var(--color-text-muted)]">Purchase Total:</span> <span className="text-[var(--color-text)]">TTD {totalAmount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></p>
              </div>
            </div>
            <div className="bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30 rounded-lg p-4 text-sm text-[var(--color-warning)]">
              In the next steps you will upload supporting documents and sign the Hire Purchase Agreement and Consent.
            </div>
          </div>
        )}

        {/* ── Step 6: Documents ─────────────────────── */}
        {step === 7 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-[var(--color-text)]">Supporting Documentation</h2>
            <p className="text-sm text-[var(--color-text-muted)]">
              Upload supporting documents for your application. You can upload multiple files per category. This step is optional.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {DOCUMENT_TYPES.map((docType) => {
                const docsOfType = documents.filter((d) => d.documentType === docType.value);
                return (
                  <div key={docType.value} className="border border-[var(--color-border)] rounded-lg p-4 bg-[var(--color-surface)] space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-[var(--color-text)]">{docType.label}</h3>
                      {docsOfType.length > 0 && (
                        <span className="text-xs bg-[var(--color-primary)]/15 text-[var(--color-primary)] px-2 py-0.5 rounded-full font-medium">{docsOfType.length}</span>
                      )}
                    </div>
                    {docsOfType.length > 0 && (
                      <div className="space-y-2">
                        {docsOfType.map((doc) => (
                          <div key={doc.id} className="flex items-center justify-between p-2 rounded bg-[var(--color-bg)] text-sm">
                            <div className="flex items-center gap-2 min-w-0">
                              <Paperclip size={14} className="text-[var(--color-primary)] shrink-0" />
                              <span className="text-[var(--color-text)] truncate">{doc.file.name}</span>
                            </div>
                            <button type="button" onClick={() => setDocuments((prev) => prev.filter((d) => d.id !== doc.id))} className="p-1 rounded hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] hover:text-[var(--color-danger)] shrink-0 ml-2">
                              <X size={14} />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                    <label className="flex items-center justify-center gap-2 w-full py-2 px-3 border border-dashed border-[var(--color-border)] rounded-lg cursor-pointer hover:border-[var(--color-primary)] hover:bg-[var(--color-primary)]/5 transition-colors text-sm text-[var(--color-text-muted)] hover:text-[var(--color-primary)]">
                      <Plus size={14} />
                      <span>Upload {docType.label}</span>
                      <input type="file" className="hidden" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => { const file = e.target.files?.[0]; if (!file) return; setDocuments((prev) => [...prev, { id: crypto.randomUUID(), documentType: docType.value, file }]); e.target.value = ''; }} />
                    </label>
                  </div>
                );
              })}
            </div>
            <p className="text-xs text-[var(--color-text-muted)]">
              Accepted: PDF, images (JPG, PNG). Max file size applies per document.
            </p>
          </div>
        )}

        {/* ── Step 7: Sign Contract ─────────────────── */}
        {step === 8 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-[var(--color-text)]">Hire Purchase Agreement and Consent</h2>

            {/* Reference */}
            {draftRef && (
              <p className="text-sm text-[var(--color-text-muted)]">Reference: <span className="font-medium text-[var(--color-text)]">{draftRef}</span></p>
            )}

            {/* ── HIRE PURCHASE AGREEMENT (full contract text) ── */}
            <HirePurchaseAgreementText
              applicantName={applicantFullName}
              applicantAddress={applicantAddress}
              referenceNumber={draftRef || undefined}
              productName={selectedProduct?.name}
              items={items.filter(it => it.category_id && parseFloat(it.price || '0') > 0).map(it => ({
                description: it.description || it.category_name || '',
                category_name: it.category_name || '',
                quantity: parseInt(it.quantity || '1', 10),
                price: parseFloat(it.price || '0'),
              }))}
              cashPrice={totalAmount}
              downpayment={calculation?.downpayment || 0}
              totalFinanced={(() => {
                const mp = calculation?.monthly_payment || 0;
                return mp > 0 ? mp * (selectedTerm || 0) : totalAmount;
              })()}
              interestAndFees={(() => {
                const mp = calculation?.monthly_payment || 0;
                const dp = calculation?.downpayment || 0;
                const amountFinanced = totalAmount - dp;
                const total = mp * (selectedTerm || 0);
                return total > amountFinanced ? total - amountFinanced : 0;
              })()}
              termMonths={selectedTerm || 0}
              monthlyPayment={calculation?.monthly_payment || 0}
            />

            {/* ── Signature ── */}
            <div className="space-y-3">
              <h3 className="font-medium text-[var(--color-text)]">Customer Signature</h3>
              <div className="border border-[var(--color-border)] rounded-lg overflow-hidden bg-[var(--color-surface)]">
                <canvas
                  ref={canvasRef}
                  className="w-full cursor-crosshair"
                  style={{ height: 140, touchAction: 'none' }}
                  onMouseDown={startDraw}
                  onMouseMove={draw}
                  onMouseUp={stopDraw}
                  onMouseLeave={stopDraw}
                  onTouchStart={startDraw}
                  onTouchMove={draw}
                  onTouchEnd={stopDraw}
                />
              </div>
              <div className="flex justify-between items-center">
                <p className="text-xs text-[var(--color-text-muted)]">Draw your signature above</p>
                <button onClick={clearSig} className="text-xs text-[var(--color-primary)] hover:underline">Clear</button>
              </div>

              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Full Name</label>
                <input
                  value={typedName}
                  onChange={(e) => setTypedName(e.target.value)}
                  placeholder="Type your full name"
                  className={inputClass}
                />
              </div>

              <label className="flex items-start gap-2 mt-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={agreed}
                  onChange={(e) => setAgreed(e.target.checked)}
                  className="mt-1 accent-[var(--color-primary)]"
                />
                <span className="text-sm text-[var(--color-text)]">
                  I have read and agree to the Hire Purchase Agreement and Consent above. I confirm my details are accurate and authorize credit checks.
                </span>
              </label>
            </div>
          </div>
        )}

        {/* ── Navigation ───────────────────────────── */}
        <div className="flex justify-between mt-8 pt-4 border-t border-[var(--color-border)]">
          <Button variant="ghost" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>
            <ChevronLeft size={16} className="mr-1" /> Previous
          </Button>
          {step === 0 ? (
            (scanPhase === 'done' || scanPhase === 'start') && (
              <Button onClick={() => { setError(''); setStep(1); }}>
                {scanPhase === 'done' ? 'Continue to Personal Info' : 'Next'} <ChevronRight size={16} className="ml-1" />
              </Button>
            )
          ) : step < 6 ? (
            <Button
              onClick={() => {
                if (step === 4 && (!merchantId || !branchId || totalAmount <= 0)) {
                  setError('Please select merchant/branch and add at least one valid item.');
                  return;
                }
                if (step === 5 && (!selectedProductId || !selectedTerm || !calculation)) {
                  setError('Please select a product and tenure, then wait for calculation.');
                  return;
                }
                setError('');
                setStep(step + 1);
              }}
              disabled={!canProceed()}
            >
              Next <ChevronRight size={16} className="ml-1" />
            </Button>
          ) : step === 6 ? (
            <Button onClick={handleCreateDraft} isLoading={submitting}>
              Continue to Documents <ChevronRight size={16} className="ml-1" />
            </Button>
          ) : step === 7 ? (
            <Button onClick={handleContinueFromDocuments} isLoading={submitting}>
              Continue to Sign <ChevronRight size={16} className="ml-1" />
            </Button>
          ) : (
            <Button
              onClick={handleSignAndSubmit}
              isLoading={submitting}
              disabled={!hasSignature || !typedName || !agreed}
            >
              Sign & Submit Application
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
