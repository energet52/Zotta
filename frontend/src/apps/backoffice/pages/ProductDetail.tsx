import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Plus, RefreshCcw, Trash2 } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { adminApi } from '../../../api/endpoints';

type Merchant = { id: number; name: string };
type ScoreRange = { id: number; min_score: number; max_score: number };
type Fee = {
  id: number;
  fee_type: string;
  fee_base: string;
  fee_amount: number;
  is_available: boolean;
};
type Product = {
  id: number;
  name: string;
  description?: string;
  merchant_id?: number | null;
  min_term_months: number;
  max_term_months: number;
  min_amount: number;
  max_amount: number;
  repayment_scheme: string;
  grace_period_days: number;
  is_active: boolean;
  score_ranges: ScoreRange[];
  fees: Fee[];
};

const FEE_TYPES = [
  'admin_fee_pct',
  'credit_fee_pct',
  'origination_fee_pct',
  'origination_fee_flat',
  'late_payment_fee_flat',
];
const FEE_BASES = ['purchase_amount', 'financed_amount', 'flat'];
const REPAYMENT_SCHEMES = [
  'Monthly Equal Installment Monthly Actual/365 (Fixed)',
  'Monthly Equal Installment (Fixed)',
  'Bi-Weekly (Fixed)',
];

export default function ProductDetail() {
  const { id } = useParams();
  const isNew = id === 'new';
  const navigate = useNavigate();
  const [tab, setTab] = useState<'general' | 'fees'>('general');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [product, setProduct] = useState<Product>({
    id: 0,
    name: '',
    description: '',
    merchant_id: null,
    min_term_months: 6,
    max_term_months: 24,
    min_amount: 2000,
    max_amount: 25000,
    repayment_scheme: REPAYMENT_SCHEMES[0],
    grace_period_days: 0,
    is_active: true,
    score_ranges: [],
    fees: [],
  });

  const [newScoreRange, setNewScoreRange] = useState({ min_score: 300, max_score: 850 });
  const [newFee, setNewFee] = useState({
    fee_type: 'admin_fee_pct',
    fee_base: 'purchase_amount',
    fee_amount: 0,
    is_available: true,
  });

  const load = async () => {
    setLoading(true);
    try {
      const [mRes, pRes] = await Promise.all([
        adminApi.getMerchants(),
        isNew ? Promise.resolve({ data: null }) : adminApi.getProduct(Number(id)),
      ]);
      setMerchants(mRes.data || []);
      if (pRes.data) setProduct(pRes.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [id]);

  const saveProduct = async () => {
    setSaving(true);
    try {
      if (isNew) {
        const res = await adminApi.createProduct({
          name: product.name,
          description: product.description,
          merchant_id: product.merchant_id || null,
          min_term_months: product.min_term_months,
          max_term_months: product.max_term_months,
          min_amount: product.min_amount,
          max_amount: product.max_amount,
          repayment_scheme: product.repayment_scheme,
          grace_period_days: product.grace_period_days,
          is_active: product.is_active,
        });
        navigate(`/backoffice/products/${res.data.id}`);
      } else {
        await adminApi.updateProduct(product.id, {
          name: product.name,
          description: product.description,
          merchant_id: product.merchant_id || null,
          min_term_months: product.min_term_months,
          max_term_months: product.max_term_months,
          min_amount: product.min_amount,
          max_amount: product.max_amount,
          repayment_scheme: product.repayment_scheme,
          grace_period_days: product.grace_period_days,
          is_active: product.is_active,
        });
        await load();
      }
    } finally {
      setSaving(false);
    }
  };

  const canManageRanges = useMemo(() => !isNew && product.id > 0, [isNew, product.id]);

  if (loading) return <div className="text-[var(--color-text-muted)]">Loading product...</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Link to="/backoffice/products">
          <Button variant="outline"><ArrowLeft size={14} className="mr-1" /> Back</Button>
        </Link>
        <Button variant="outline" onClick={load}><RefreshCcw size={14} className="mr-1" /> Refresh</Button>
      </div>

      <h1 className="text-2xl font-bold">General Product Details</h1>

      <Card padding="none">
        <div className="border-b border-[var(--color-border)] px-4 py-2 flex items-center gap-2">
          <button
            className={`px-3 py-1.5 rounded-lg text-sm ${tab === 'general' ? 'bg-[var(--color-surface-hover)]' : 'text-[var(--color-text-muted)]'}`}
            onClick={() => setTab('general')}
          >
            General Parameters
          </button>
          <button
            className={`px-3 py-1.5 rounded-lg text-sm ${tab === 'fees' ? 'bg-[var(--color-surface-hover)]' : 'text-[var(--color-text-muted)]'}`}
            onClick={() => setTab('fees')}
          >
            Repayment Scheme and Fee
          </button>
        </div>

        {tab === 'general' && (
          <div className="p-4 grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Product Name</label>
                <input
                  value={product.name}
                  onChange={(e) => setProduct((p) => ({ ...p, name: e.target.value }))}
                  className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg"
                />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Product Description</label>
                <textarea
                  rows={3}
                  value={product.description || ''}
                  onChange={(e) => setProduct((p) => ({ ...p, description: e.target.value }))}
                  className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg"
                />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Merchant</label>
                <select
                  value={product.merchant_id ?? ''}
                  onChange={(e) => setProduct((p) => ({ ...p, merchant_id: e.target.value ? Number(e.target.value) : null }))}
                  className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg"
                >
                  <option value="">All Merchants</option>
                  {merchants.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-[var(--color-text-muted)] mb-1">Min Term (months)</label>
                  <input type="number" value={product.min_term_months} onChange={(e) => setProduct((p) => ({ ...p, min_term_months: Number(e.target.value) }))} className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                </div>
                <div>
                  <label className="block text-xs text-[var(--color-text-muted)] mb-1">Max Term (months)</label>
                  <input type="number" value={product.max_term_months} onChange={(e) => setProduct((p) => ({ ...p, max_term_months: Number(e.target.value) }))} className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-[var(--color-text-muted)] mb-1">Min Amount</label>
                  <input type="number" value={product.min_amount} onChange={(e) => setProduct((p) => ({ ...p, min_amount: Number(e.target.value) }))} className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                </div>
                <div>
                  <label className="block text-xs text-[var(--color-text-muted)] mb-1">Max Amount</label>
                  <input type="number" value={product.max_amount} onChange={(e) => setProduct((p) => ({ ...p, max_amount: Number(e.target.value) }))} className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                </div>
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-semibold">Product Score Range</h3>
                {canManageRanges && (
                  <Button
                    size="sm"
                    onClick={async () => {
                      await adminApi.createScoreRange(product.id, newScoreRange);
                      setNewScoreRange({ min_score: 300, max_score: 850 });
                      await load();
                    }}
                  >
                    <Plus size={14} className="mr-1" /> Add
                  </Button>
                )}
              </div>

              <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                      <th className="px-3 py-2 text-left">Min Score (included)</th>
                      <th className="px-3 py-2 text-left">Max Score (excluded)</th>
                      <th className="px-3 py-2 text-left">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {product.score_ranges.map((sr) => (
                      <tr key={sr.id} className="border-b border-[var(--color-border)]">
                        <td className="px-3 py-2">{sr.min_score}</td>
                        <td className="px-3 py-2">{sr.max_score}</td>
                        <td className="px-3 py-2">
                          <button
                            className="text-red-400 hover:text-red-300"
                            onClick={async () => {
                              await adminApi.deleteScoreRange(sr.id);
                              await load();
                            }}
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                    {product.score_ranges.length === 0 && (
                      <tr>
                        <td className="px-3 py-3 text-[var(--color-text-muted)]" colSpan={3}>No score ranges yet</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              {canManageRanges && (
                <div className="grid grid-cols-2 gap-2 mt-3">
                  <input
                    type="number"
                    placeholder="Min score"
                    value={newScoreRange.min_score}
                    onChange={(e) => setNewScoreRange((s) => ({ ...s, min_score: Number(e.target.value) }))}
                    className="h-[38px] px-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm"
                  />
                  <input
                    type="number"
                    placeholder="Max score"
                    value={newScoreRange.max_score}
                    onChange={(e) => setNewScoreRange((s) => ({ ...s, max_score: Number(e.target.value) }))}
                    className="h-[38px] px-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm"
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {tab === 'fees' && (
          <div className="p-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Repayment Scheme</label>
                <select
                  value={product.repayment_scheme}
                  onChange={(e) => setProduct((p) => ({ ...p, repayment_scheme: e.target.value }))}
                  className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg"
                >
                  {REPAYMENT_SCHEMES.map((rs) => <option key={rs} value={rs}>{rs}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Grace Period</label>
                <input
                  type="number"
                  value={product.grace_period_days}
                  onChange={(e) => setProduct((p) => ({ ...p, grace_period_days: Number(e.target.value) }))}
                  className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg"
                />
              </div>
            </div>

            <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                    <th className="px-3 py-2 text-left">Fee Type</th>
                    <th className="px-3 py-2 text-left">Fee Base</th>
                    <th className="px-3 py-2 text-left">Fee Amount</th>
                    <th className="px-3 py-2 text-left">Available</th>
                    <th className="px-3 py-2 text-left">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {product.fees.map((fee) => (
                    <tr key={fee.id} className="border-b border-[var(--color-border)]">
                      <td className="px-3 py-2">{fee.fee_type}</td>
                      <td className="px-3 py-2">{fee.fee_base}</td>
                      <td className="px-3 py-2">{fee.fee_amount}</td>
                      <td className="px-3 py-2">{fee.is_available ? 'Yes' : 'No'}</td>
                      <td className="px-3 py-2">
                        <button
                          className="text-red-400 hover:text-red-300 inline-flex items-center gap-1"
                          onClick={async () => {
                            await adminApi.deleteFee(fee.id);
                            await load();
                          }}
                        >
                          <Trash2 size={14} /> Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                  {product.fees.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-3 py-3 text-[var(--color-text-muted)]">No fees configured</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {canManageRanges && (
              <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
                <select value={newFee.fee_type} onChange={(e) => setNewFee((f) => ({ ...f, fee_type: e.target.value }))} className="h-[38px] px-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm">
                  {FEE_TYPES.map((ft) => <option key={ft} value={ft}>{ft}</option>)}
                </select>
                <select value={newFee.fee_base} onChange={(e) => setNewFee((f) => ({ ...f, fee_base: e.target.value }))} className="h-[38px] px-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm">
                  {FEE_BASES.map((fb) => <option key={fb} value={fb}>{fb}</option>)}
                </select>
                <input type="number" value={newFee.fee_amount} onChange={(e) => setNewFee((f) => ({ ...f, fee_amount: Number(e.target.value) }))} className="h-[38px] px-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm" />
                <label className="inline-flex items-center gap-2 px-3 py-2 border border-[var(--color-border)] rounded-lg">
                  <input type="checkbox" checked={newFee.is_available} onChange={(e) => setNewFee((f) => ({ ...f, is_available: e.target.checked }))} />
                  <span>Available</span>
                </label>
                <Button
                  onClick={async () => {
                    await adminApi.createFee(product.id, newFee);
                    setNewFee({ fee_type: 'admin_fee_pct', fee_base: 'purchase_amount', fee_amount: 0, is_available: true });
                    await load();
                  }}
                >
                  <Plus size={14} className="mr-1" /> Add Fee
                </Button>
              </div>
            )}
          </div>
        )}

        <div className="border-t border-[var(--color-border)] p-4 flex items-center justify-between">
          <Button variant="ghost" onClick={() => navigate('/backoffice/products')}>Cancel &amp; Close</Button>
          <Button onClick={saveProduct} isLoading={saving}>Save</Button>
        </div>
      </Card>
    </div>
  );
}
