import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Check, Plus, Trash2 } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { catalogApi, loanApi } from '../../../api/endpoints';

const STEPS = ['Shopping', 'Plan Selection', 'Personal Info', 'Employment', 'Review'];

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

function SearchableSelect({
  value,
  onChange,
  options,
  placeholder,
}: {
  value: number | null;
  onChange: (id: number, label: string) => void;
  options: Array<{ id: number; name: string }>;
  placeholder: string;
}) {
  const [query, setQuery] = useState('');
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.name.toLowerCase().includes(q));
  }, [query, options]);

  return (
    <div className="space-y-2">
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={`Search ${placeholder.toLowerCase()}...`}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
      />
      <select
        value={value ?? ''}
        onChange={(e) => {
          const id = Number(e.target.value);
          const selected = options.find((o) => o.id === id);
          if (selected) onChange(selected.id, selected.name);
        }}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
      >
        <option value="">Select {placeholder}</option>
        {filtered.map((o) => (
          <option key={o.id} value={o.id}>{o.name}</option>
        ))}
      </select>
    </div>
  );
}

export default function LoanApplication() {
  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

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
    date_of_birth: '', national_id: '', gender: '', marital_status: '',
    address_line1: '', address_line2: '', city: '', parish: '',
  });
  const [employment, setEmployment] = useState({
    employer_name: '', job_title: '', employment_type: '', years_employed: '',
    monthly_income: '', other_income: '', monthly_expenses: '', existing_debt: '', dependents: '',
  });

  const totalAmount = useMemo(
    () => items.reduce((sum, it) => sum + (parseFloat(it.price || '0') * parseInt(it.quantity || '0', 10)), 0),
    [items],
  );

  const selectedProduct = products.find((p) => p.id === selectedProductId) || null;
  const termOptions = useMemo(() => {
    if (!selectedProduct) return [];
    const out: number[] = [];
    for (let t = selectedProduct.min_term_months; t <= selectedProduct.max_term_months; t += 1) out.push(t);
    return out;
  }, [selectedProduct]);

  useEffect(() => {
    (async () => {
      try {
        const [mRes, cRes] = await Promise.all([catalogApi.getMerchants(), catalogApi.getCategories()]);
        setMerchants(mRes.data || []);
        setCategories(cRes.data || []);
      } catch {
        // ignore
      }
      try {
        const pRes = await loanApi.getProfile();
        const p = pRes.data;
        setProfile((prev) => ({
          ...prev,
          date_of_birth: p.date_of_birth || '',
          national_id: p.national_id || '',
          gender: p.gender || '',
          marital_status: p.marital_status || '',
          address_line1: p.address_line1 || '',
          address_line2: p.address_line2 || '',
          city: p.city || '',
          parish: p.parish || '',
        }));
        setEmployment((prev) => ({
          ...prev,
          employer_name: p.employer_name || '',
          job_title: p.job_title || '',
          employment_type: p.employment_type || '',
          years_employed: p.years_employed != null ? String(p.years_employed) : '',
          monthly_income: p.monthly_income != null ? String(p.monthly_income) : '',
          other_income: p.other_income != null ? String(p.other_income) : '',
          monthly_expenses: p.monthly_expenses != null ? String(p.monthly_expenses) : '',
          existing_debt: p.existing_debt != null ? String(p.existing_debt) : '',
          dependents: p.dependents != null ? String(p.dependents) : '',
        }));
      } catch {
        // first-time customer
      }
    })();
  }, []);

  useEffect(() => {
    if (!merchantId) {
      setBranches([]);
      setBranchId(null);
      return;
    }
    catalogApi.getBranches(merchantId)
      .then((res) => setBranches(res.data || []))
      .catch(() => setBranches([]));
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

  const emptyToUndef = (v: string) => (v === '' ? undefined : v);

  const handleSubmit = async () => {
    if (!merchantId || !branchId || !selectedProductId || !selectedTerm) {
      setError('Please complete shopping and product selection before submitting.');
      return;
    }

    setSubmitting(true);
    setError('');
    try {
      await loanApi.updateProfile({
        date_of_birth: emptyToUndef(profile.date_of_birth),
        national_id: emptyToUndef(profile.national_id),
        gender: emptyToUndef(profile.gender),
        marital_status: emptyToUndef(profile.marital_status),
        address_line1: emptyToUndef(profile.address_line1),
        address_line2: emptyToUndef(profile.address_line2),
        city: emptyToUndef(profile.city),
        parish: emptyToUndef(profile.parish),
        years_employed: employment.years_employed ? parseInt(employment.years_employed, 10) : undefined,
        monthly_income: employment.monthly_income ? parseFloat(employment.monthly_income) : undefined,
        other_income: employment.other_income ? parseFloat(employment.other_income) : undefined,
        monthly_expenses: employment.monthly_expenses ? parseFloat(employment.monthly_expenses) : undefined,
        existing_debt: employment.existing_debt ? parseFloat(employment.existing_debt) : undefined,
        dependents: employment.dependents ? parseInt(employment.dependents, 10) : undefined,
        employer_name: emptyToUndef(employment.employer_name),
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
      await loanApi.submit(appId);
      navigate(`/applications/${appId}`);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') setError(detail);
      else if (Array.isArray(detail)) setError(detail.map((e: any) => e.msg || String(e)).join('; '));
      else setError('Failed to submit application');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Hire-Purchase Application</h1>
      <div className="flex items-center mb-8">
        {STEPS.map((label, i) => (
          <div key={label} className="flex items-center flex-1">
            <div className="flex items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${i < step ? 'bg-green-500 text-white' : i === step ? 'bg-[var(--color-primary)] text-white' : 'bg-gray-200 text-gray-500'}`}>
                {i < step ? <Check size={16} /> : i + 1}
              </div>
              <span className={`ml-2 text-sm hidden sm:inline ${i === step ? 'font-medium text-gray-900' : 'text-gray-500'}`}>{label}</span>
            </div>
            {i < STEPS.length - 1 && <div className="flex-1 h-px bg-gray-200 mx-3" />}
          </div>
        ))}
      </div>

      {error && <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>}

      <Card padding="lg">
        {step === 0 && (
          <div className="space-y-5">
            <h2 className="text-lg font-semibold">Shopping Context</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Merchant</label>
                <SearchableSelect
                  value={merchantId}
                  options={merchants}
                  placeholder="Merchant"
                  onChange={(id) => setMerchantId(id)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Branch</label>
                <select
                  value={branchId ?? ''}
                  onChange={(e) => setBranchId(e.target.value ? Number(e.target.value) : null)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="">Select branch</option>
                  {branches.map((b) => <option key={b.id} value={b.id}>{b.name}{b.is_online ? ' (Online)' : ''}</option>)}
                </select>
              </div>
            </div>

            <h3 className="font-medium">Items for Installments</h3>
            <div className="space-y-3">
              {items.map((item, idx) => (
                <div key={idx} className="grid grid-cols-1 md:grid-cols-6 gap-2 items-end border border-gray-200 rounded-lg p-3">
                  <div className="md:col-span-2">
                    <label className="block text-xs text-gray-500 mb-1">Category</label>
                    <SearchableSelect
                      value={item.category_id}
                      options={categories}
                      placeholder="Category"
                      onChange={(id, label) => setItems((prev) => prev.map((it, i) => i === idx ? { ...it, category_id: id, category_name: label } : it))}
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Price</label>
                    <input
                      type="number"
                      value={item.price}
                      onChange={(e) => setItems((prev) => prev.map((it, i) => i === idx ? { ...it, price: e.target.value } : it))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Qty</label>
                    <input
                      type="number"
                      min={1}
                      value={item.quantity}
                      onChange={(e) => setItems((prev) => prev.map((it, i) => i === idx ? { ...it, quantity: e.target.value } : it))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Description</label>
                    <input
                      value={item.description}
                      onChange={(e) => setItems((prev) => prev.map((it, i) => i === idx ? { ...it, description: e.target.value } : it))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    />
                  </div>
                  <div className="flex justify-end">
                    <button
                      className="text-red-500"
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
              <p className="text-sm text-gray-500">Total Purchase Amount</p>
              <p className="text-2xl font-bold">TTD {totalAmount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Select Credit Product & Tenure</h2>
            {products.length === 0 ? (
              <p className="text-sm text-gray-500">No eligible products for current merchant and amount.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {products.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => {
                      setSelectedProductId(p.id);
                      setSelectedTerm(null);
                    }}
                    className={`text-left border rounded-lg p-4 ${selectedProductId === p.id ? 'border-[var(--color-primary)] ring-2 ring-[var(--color-primary)]/20' : 'border-gray-200'}`}
                  >
                    <p className="font-semibold">{p.name}</p>
                    <p className="text-sm text-gray-500">{p.description || 'No description'}</p>
                    <p className="text-xs text-gray-500 mt-2">
                      Term {p.min_term_months}-{p.max_term_months} months • Amount {p.min_amount.toLocaleString()} - {p.max_amount.toLocaleString()}
                    </p>
                  </button>
                ))}
              </div>
            )}
            {selectedProduct && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Tenure</label>
                  <select
                    value={selectedTerm ?? ''}
                    onChange={(e) => setSelectedTerm(e.target.value ? Number(e.target.value) : null)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  >
                    <option value="">Select tenure</option>
                    {termOptions.map((t) => <option key={t} value={t}>{t} months</option>)}
                  </select>
                </div>
              </div>
            )}
            {calculation && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="p-3 bg-gray-50 rounded-lg"><p className="text-xs text-gray-500">Total Financed</p><p className="font-bold">TTD {calculation.total_financed.toLocaleString()}</p></div>
                  <div className="p-3 bg-gray-50 rounded-lg"><p className="text-xs text-gray-500">Downpayment</p><p className="font-bold">TTD {calculation.downpayment.toLocaleString()}</p></div>
                  <div className="p-3 bg-gray-50 rounded-lg"><p className="text-xs text-gray-500">Fees Upfront</p><p className="font-bold">TTD {calculation.fees_due_upfront.toLocaleString()}</p></div>
                  <div className="p-3 bg-blue-50 rounded-lg"><p className="text-xs text-blue-600">Monthly Payment</p><p className="font-bold text-blue-700">TTD {calculation.monthly_payment.toLocaleString()}</p></div>
                </div>
                <div>
                  <h3 className="font-medium mb-2">Fees Breakdown</h3>
                  <div className="border border-gray-200 rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead><tr className="bg-gray-50"><th className="px-3 py-2 text-left">Fee Type</th><th className="px-3 py-2 text-left">Base</th><th className="px-3 py-2 text-left">Amount</th></tr></thead>
                      <tbody>
                        {calculation.fees_breakdown.map((f, i) => (
                          <tr key={i} className="border-t border-gray-100">
                            <td className="px-3 py-2">{f.fee_type}</td>
                            <td className="px-3 py-2">{f.fee_base}</td>
                            <td className="px-3 py-2">TTD {f.fee_amount.toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                <div>
                  <h3 className="font-medium mb-2">Payment Calendar</h3>
                  <div className="border border-gray-200 rounded-lg overflow-auto max-h-72">
                    <table className="w-full text-sm">
                      <thead><tr className="bg-gray-50"><th className="px-3 py-2 text-left">#</th><th className="px-3 py-2 text-left">Due Date</th><th className="px-3 py-2 text-left">Principal</th><th className="px-3 py-2 text-left">Interest</th><th className="px-3 py-2 text-left">Amount Due</th></tr></thead>
                      <tbody>
                        {calculation.payment_calendar.map((row) => (
                          <tr key={row.installment_number} className="border-t border-gray-100">
                            <td className="px-3 py-2">{row.installment_number}</td>
                            <td className="px-3 py-2">{new Date(row.due_date).toLocaleDateString()}</td>
                            <td className="px-3 py-2">TTD {row.principal.toLocaleString()}</td>
                            <td className="px-3 py-2">TTD {row.interest.toLocaleString()}</td>
                            <td className="px-3 py-2 font-medium">TTD {row.amount_due.toLocaleString()}</td>
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

        {step === 2 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Personal Information</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input name="date_of_birth" type="date" value={profile.date_of_birth} onChange={(e) => setProfile({ ...profile, date_of_birth: e.target.value })} className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              <input name="national_id" value={profile.national_id} onChange={(e) => setProfile({ ...profile, national_id: e.target.value })} placeholder="National ID" className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              <select name="gender" value={profile.gender} onChange={(e) => setProfile({ ...profile, gender: e.target.value })} className="px-3 py-2 border border-gray-300 rounded-lg text-sm">
                <option value="">Gender</option><option value="male">Male</option><option value="female">Female</option><option value="other">Other</option>
              </select>
              <select name="marital_status" value={profile.marital_status} onChange={(e) => setProfile({ ...profile, marital_status: e.target.value })} className="px-3 py-2 border border-gray-300 rounded-lg text-sm">
                <option value="">Marital Status</option><option value="single">Single</option><option value="married">Married</option><option value="divorced">Divorced</option><option value="widowed">Widowed</option>
              </select>
            </div>
            <input value={profile.address_line1} onChange={(e) => setProfile({ ...profile, address_line1: e.target.value })} placeholder="Address line 1" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            <input value={profile.address_line2} onChange={(e) => setProfile({ ...profile, address_line2: e.target.value })} placeholder="Address line 2 (optional)" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input value={profile.city} onChange={(e) => setProfile({ ...profile, city: e.target.value })} placeholder="City" className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              <input value={profile.parish} onChange={(e) => setProfile({ ...profile, parish: e.target.value })} placeholder="Parish" className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Employment & Income</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input value={employment.employer_name} onChange={(e) => setEmployment({ ...employment, employer_name: e.target.value })} placeholder="Employer name" className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              <input value={employment.job_title} onChange={(e) => setEmployment({ ...employment, job_title: e.target.value })} placeholder="Job title" className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              <select value={employment.employment_type} onChange={(e) => setEmployment({ ...employment, employment_type: e.target.value })} className="px-3 py-2 border border-gray-300 rounded-lg text-sm">
                <option value="">Employment Type</option><option value="employed">Employed</option><option value="self_employed">Self-Employed</option><option value="contract">Contract</option>
              </select>
              <input type="number" value={employment.years_employed} onChange={(e) => setEmployment({ ...employment, years_employed: e.target.value })} placeholder="Years employed" className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              <input type="number" value={employment.monthly_income} onChange={(e) => setEmployment({ ...employment, monthly_income: e.target.value })} placeholder="Monthly income" className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              <input type="number" value={employment.other_income} onChange={(e) => setEmployment({ ...employment, other_income: e.target.value })} placeholder="Other income" className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              <input type="number" value={employment.monthly_expenses} onChange={(e) => setEmployment({ ...employment, monthly_expenses: e.target.value })} placeholder="Monthly expenses" className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              <input type="number" value={employment.existing_debt} onChange={(e) => setEmployment({ ...employment, existing_debt: e.target.value })} placeholder="Existing debt" className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            </div>
            <input type="number" value={employment.dependents} onChange={(e) => setEmployment({ ...employment, dependents: e.target.value })} placeholder="Number of dependents" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
          </div>
        )}

        {step === 4 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Review & Submit</h2>
            <div className="bg-gray-50 rounded-lg p-4 space-y-2 text-sm">
              <p><span className="text-gray-500">Merchant:</span> {merchants.find((m) => m.id === merchantId)?.name || '—'}</p>
              <p><span className="text-gray-500">Branch:</span> {branches.find((b) => b.id === branchId)?.name || '—'}</p>
              <p><span className="text-gray-500">Product:</span> {selectedProduct?.name || '—'}</p>
              <p><span className="text-gray-500">Term:</span> {selectedTerm || '—'} months</p>
              <p><span className="text-gray-500">Purchase Total:</span> TTD {totalAmount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
              <p><span className="text-gray-500">Downpayment:</span> TTD {(calculation?.downpayment || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
              <p><span className="text-gray-500">Fees Upfront:</span> TTD {(calculation?.fees_due_upfront || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
              <p><span className="text-gray-500">Monthly Payment:</span> TTD {(calculation?.monthly_payment || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
            </div>
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm text-yellow-800">
              By submitting, you confirm your personal details and purchase information are accurate and authorize credit checks.
            </div>
          </div>
        )}

        <div className="flex justify-between mt-8 pt-4 border-t border-gray-100">
          <Button variant="ghost" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>
            <ChevronLeft size={16} className="mr-1" /> Previous
          </Button>
          {step < STEPS.length - 1 ? (
            <Button
              onClick={() => {
                if (step === 0 && (!merchantId || !branchId || totalAmount <= 0)) {
                  setError('Please select merchant/branch and add at least one valid item.');
                  return;
                }
                if (step === 1 && (!selectedProductId || !selectedTerm || !calculation)) {
                  setError('Please select a product and tenure, then wait for calculation.');
                  return;
                }
                setError('');
                setStep(step + 1);
              }}
            >
              Next <ChevronRight size={16} className="ml-1" />
            </Button>
          ) : (
            <Button onClick={handleSubmit} isLoading={submitting}>
              Submit Application
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
