import { useEffect, useMemo, useState, useCallback, useRef } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, Plus, RefreshCcw, Trash2, Copy, Send,
  BarChart3, Brain, Beaker, Shield, Layers, Settings2,
  TrendingUp, TrendingDown, AlertTriangle, CheckCircle2,
  Sparkles, ChevronRight, Activity, Target, Zap, Globe,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { adminApi } from '../../../api/endpoints';

/* ────────────────────────── Types ────────────────────────── */

type Merchant = { id: number; name: string };
type ScoreRange = { id: number; min_score: number; max_score: number };
type Fee = { id: number; fee_type: string; fee_base: string; fee_amount: number; is_available: boolean };
type RateTier = {
  id: number; tier_name: string; min_score: number; max_score: number;
  interest_rate: number; max_ltv_pct?: number | null; max_dti_pct?: number | null; is_active: boolean;
};
type EligibilityCriteria = {
  min_age?: number | null; max_age?: number | null; min_income?: number | null;
  max_dti?: number | null; employment_types?: string[]; min_employment_months?: number | null;
  required_documents?: string[]; excluded_sectors?: string[];
  citizenship_required?: boolean; existing_customer_only?: boolean;
};
type Product = {
  id: number; name: string; description?: string; merchant_id?: number | null;
  min_term_months: number; max_term_months: number; min_amount: number; max_amount: number;
  repayment_scheme: string; grace_period_days: number; is_active: boolean;
  interest_rate?: number | null;
  eligibility_criteria?: EligibilityCriteria | null;
  lifecycle_status?: string;
  version?: number;
  channels?: string[] | null;
  target_segments?: string[] | null;
  internal_notes?: string | null;
  regulatory_code?: string | null;
  ai_summary?: string | null;
  score_ranges: ScoreRange[]; fees: Fee[]; rate_tiers?: RateTier[];
};

type HealthFactor = { name: string; score: number; weight: number; detail: string };
type Analytics = {
  metrics: {
    total_applications: number; recent_applications_30d: number;
    status_breakdown: Record<string, number>; approval_rate: number;
    avg_loan_amount: number; avg_term_months: number;
    total_disbursed_volume: number; total_collected: number;
    monthly_trend: { month: string; applications: number }[];
  };
  health: { score: number; status: string; factors: HealthFactor[] };
};
type ChatMsg = { role: 'user' | 'assistant'; content: string };

/* ────────────────────────── Constants ────────────────────────── */

const FEE_TYPES = ['admin_fee_pct', 'credit_fee_pct', 'origination_fee_pct', 'origination_fee_flat', 'late_payment_fee_flat'];
const FEE_BASES = ['purchase_amount', 'financed_amount', 'flat'];
const REPAYMENT_SCHEMES = [
  'Monthly Equal Installment Monthly Actual/365 (Fixed)',
  'Monthly Equal Installment (Fixed)',
  'Bi-Weekly (Fixed)',
];
const LIFECYCLE_STATUSES = ['draft', 'active', 'sunset', 'retired'];
const CHANNEL_OPTIONS = ['online', 'in-store', 'whatsapp', 'agent', 'partner'];
const SEGMENT_OPTIONS = ['salaried', 'self-employed', 'pensioner', 'student', 'micro-business', 'prime', 'near-prime', 'sub-prime'];
const EMPLOYMENT_TYPES = ['Full-time', 'Part-time', 'Self-employed', 'Contract', 'Temporary', 'Retired', 'Student'];
const DOCUMENT_OPTIONS = ['National ID', 'Passport', 'Driver\'s License', 'Utility Bill', 'Pay Slip', 'Bank Statement', 'Employment Letter', 'Tax Return'];

type TabKey = 'general' | 'fees' | 'pricing' | 'eligibility' | 'analytics' | 'advisor' | 'simulator';

/* ────────────────────────── Component ────────────────────────── */

export default function ProductDetail() {
  const { id } = useParams();
  const isNew = id === 'new';
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabKey>('general');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [merchants, setMerchants] = useState<Merchant[]>([]);

  const [product, setProduct] = useState<Product>({
    id: 0, name: '', description: '', merchant_id: null,
    min_term_months: 6, max_term_months: 24, min_amount: 2000, max_amount: 25000,
    repayment_scheme: REPAYMENT_SCHEMES[0], grace_period_days: 0, is_active: true,
    interest_rate: null, eligibility_criteria: null,
    lifecycle_status: 'active', channels: [], target_segments: [],
    internal_notes: '', regulatory_code: '', score_ranges: [], fees: [], rate_tiers: [],
  });

  // Pending items for new products
  const [pendingScoreRanges, setPendingScoreRanges] = useState<{ min_score: number; max_score: number }[]>([]);
  const [pendingFees, setPendingFees] = useState<{ fee_type: string; fee_base: string; fee_amount: number; is_available: boolean }[]>([]);
  const [pendingRateTiers, setPendingRateTiers] = useState<Omit<RateTier, 'id'>[]>([]);

  // Form inputs
  const [newScoreRange, setNewScoreRange] = useState({ min_score: 300, max_score: 850 });
  const [newFee, setNewFee] = useState({ fee_type: 'admin_fee_pct', fee_base: 'purchase_amount', fee_amount: 0, is_available: true });
  const [newTier, setNewTier] = useState({ tier_name: '', min_score: 0, max_score: 0, interest_rate: 0, max_ltv_pct: '', max_dti_pct: '', is_active: true });

  // Analytics & AI
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Simulator
  const [simChanges, setSimChanges] = useState<Record<string, string>>({});
  const [simResult, setSimResult] = useState<any>(null);
  const [simLoading, setSimLoading] = useState(false);

  // AI generate
  const [generatePrompt, setGeneratePrompt] = useState('');
  const [generating, setGenerating] = useState(false);

  const load = useCallback(async () => {
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
  }, [id, isNew]);

  useEffect(() => { load(); }, [load]);

  // Auto-scroll chat
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chatMessages]);

  /* ── Save ── */
  const saveProduct = async () => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
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
        interest_rate: product.interest_rate || null,
        eligibility_criteria: product.eligibility_criteria || null,
        lifecycle_status: product.lifecycle_status || 'active',
        channels: product.channels || [],
        target_segments: product.target_segments || [],
        internal_notes: product.internal_notes || '',
        regulatory_code: product.regulatory_code || '',
      };
      if (isNew) {
        const res = await adminApi.createProduct(payload);
        const newId = res.data.id;
        for (const sr of pendingScoreRanges) await adminApi.createScoreRange(newId, sr);
        for (const fee of pendingFees) await adminApi.createFee(newId, fee);
        for (const rt of pendingRateTiers) {
          await adminApi.createRateTier(newId, {
            tier_name: rt.tier_name,
            min_score: rt.min_score,
            max_score: rt.max_score,
            interest_rate: rt.interest_rate,
            max_ltv_pct: rt.max_ltv_pct ?? undefined,
            max_dti_pct: rt.max_dti_pct ?? undefined,
            is_active: rt.is_active,
          });
        }
        navigate(`/backoffice/products/${newId}`);
      } else {
        await adminApi.updateProduct(product.id, payload);
        await load();
      }
    } finally {
      setSaving(false);
    }
  };

  /* ── Clone ── */
  const cloneProduct = async () => {
    if (isNew) return;
    try {
      const res = await adminApi.cloneProduct(product.id);
      navigate(`/backoffice/products/${res.data.id}`);
    } catch { /* ignore */ }
  };

  /* ── Analytics ── */
  const loadAnalytics = async () => {
    if (isNew) return;
    setAnalyticsLoading(true);
    try {
      const res = await adminApi.getProductAnalytics(product.id);
      setAnalytics(res.data);
    } catch { /* ignore */ }
    finally { setAnalyticsLoading(false); }
  };

  /* ── AI Chat ── */
  const sendChat = async () => {
    if (!chatInput.trim()) return;
    const question = chatInput.trim();
    setChatInput('');
    const newMsgs: ChatMsg[] = [...chatMessages, { role: 'user', content: question }];
    setChatMessages(newMsgs);
    setChatLoading(true);
    try {
      const res = await adminApi.productAdvisor({
        product_id: isNew ? undefined : product.id,
        question,
        conversation_history: newMsgs.map(m => ({ role: m.role, content: m.content })),
      });
      setChatMessages([...newMsgs, { role: 'assistant', content: res.data.answer }]);
    } catch {
      setChatMessages([...newMsgs, { role: 'assistant', content: 'Sorry, an error occurred.' }]);
    } finally { setChatLoading(false); }
  };

  /* ── Simulator ── */
  const runSimulation = async () => {
    if (isNew) return;
    setSimLoading(true);
    try {
      const changes: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(simChanges)) {
        if (v) changes[k] = isNaN(Number(v)) ? v : Number(v);
      }
      const res = await adminApi.productSimulate({ product_id: product.id, changes });
      setSimResult(res.data);
    } catch { /* ignore */ }
    finally { setSimLoading(false); }
  };

  /* ── AI Generate ── */
  const aiGenerate = async () => {
    if (!generatePrompt.trim()) return;
    setGenerating(true);
    try {
      const res = await adminApi.productGenerate({ description: generatePrompt.trim() });
      const gen = res.data.product;
      if (gen) {
        setProduct(p => ({
          ...p,
          name: gen.name || p.name,
          description: gen.description || p.description,
          min_term_months: gen.min_term_months || p.min_term_months,
          max_term_months: gen.max_term_months || p.max_term_months,
          min_amount: gen.min_amount || p.min_amount,
          max_amount: gen.max_amount || p.max_amount,
          repayment_scheme: gen.repayment_scheme || p.repayment_scheme,
          grace_period_days: gen.grace_period_days ?? p.grace_period_days,
        }));
        if (gen.score_ranges?.length) setPendingScoreRanges(gen.score_ranges);
        if (gen.fees?.length) setPendingFees(gen.fees);
        setChatMessages(prev => [...prev, { role: 'assistant', content: `**Product Generated**\n\n**${gen.name}**\n\n${gen.rationale || ''}\n\n**Target:** ${gen.target_segment || 'N/A'}\n\n**Risk:** ${gen.risk_assessment || 'N/A'}` }]);
      }
    } catch { /* ignore */ }
    finally { setGenerating(false); }
  };

  /* ── Eligibility helpers ── */
  const elig = product.eligibility_criteria || {};
  const setElig = (patch: Partial<EligibilityCriteria>) => {
    setProduct(p => ({ ...p, eligibility_criteria: { ...elig, ...patch } }));
  };

  const toggleArrayItem = (arr: string[] | undefined, item: string): string[] => {
    const current = arr || [];
    return current.includes(item) ? current.filter(x => x !== item) : [...current, item];
  };

  if (loading) return <div className="text-[var(--color-text-muted)] p-8">Loading product...</div>;

  const lifecycleColor: Record<string, string> = {
    draft: 'bg-yellow-500/20 text-yellow-400',
    active: 'bg-green-500/20 text-green-400',
    sunset: 'bg-orange-500/20 text-orange-400',
    retired: 'bg-red-500/20 text-red-400',
  };

  const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
    { key: 'general', label: 'General', icon: <Settings2 size={14} /> },
    { key: 'fees', label: 'Fees & Repayment', icon: <Layers size={14} /> },
    { key: 'pricing', label: 'Risk Pricing', icon: <TrendingUp size={14} /> },
    { key: 'eligibility', label: 'Eligibility', icon: <Shield size={14} /> },
    ...(!isNew ? [
      { key: 'analytics' as TabKey, label: 'Analytics', icon: <BarChart3 size={14} /> },
      { key: 'simulator' as TabKey, label: 'Simulator', icon: <Beaker size={14} /> },
    ] : []),
    { key: 'advisor', label: 'AI Advisor', icon: <Brain size={14} /> },
  ];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <Link to="/backoffice/products">
            <Button variant="outline" size="sm"><ArrowLeft size={14} className="mr-1" /> Back</Button>
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold">{isNew ? 'New Product' : product.name}</h1>
              {!isNew && (
                <span className={`text-xs px-2 py-0.5 rounded-full ${lifecycleColor[product.lifecycle_status || 'active']}`}>
                  {product.lifecycle_status || 'active'}
                </span>
              )}
              {!isNew && <span className="text-xs text-[var(--color-text-muted)]">v{product.version || 1}</span>}
            </div>
            {!isNew && product.ai_summary && (
              <p className="text-xs text-[var(--color-text-muted)] mt-0.5 max-w-xl truncate">{product.ai_summary}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!isNew && (
            <Button variant="outline" size="sm" onClick={cloneProduct}>
              <Copy size={14} className="mr-1" /> Clone
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCcw size={14} className="mr-1" /> Refresh
          </Button>
        </div>
      </div>

      {/* AI Product Generator (for new products) */}
      {isNew && (
        <Card>
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400"><Sparkles size={20} /></div>
            <div className="flex-1">
              <h3 className="font-semibold text-sm mb-1">AI Product Generator</h3>
              <p className="text-xs text-[var(--color-text-muted)] mb-2">Describe the product you want and AI will generate the configuration</p>
              <div className="flex gap-2">
                <input
                  value={generatePrompt}
                  onChange={e => setGeneratePrompt(e.target.value)}
                  placeholder="e.g. A small personal loan for first-time borrowers with low credit scores, max TTD 10,000..."
                  className="flex-1 px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm"
                  onKeyDown={e => e.key === 'Enter' && aiGenerate()}
                />
                <Button onClick={aiGenerate} isLoading={generating} size="sm">
                  <Sparkles size={14} className="mr-1" /> Generate
                </Button>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Tabs */}
      <Card padding="none">
        <div className="border-b border-[var(--color-border)] px-2 py-1.5 flex items-center gap-1 overflow-x-auto">
          {TABS.map(t => (
            <button
              key={t.key}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                tab === t.key ? 'bg-[var(--color-surface-hover)] text-[var(--color-text)]' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
              }`}
              onClick={() => {
                setTab(t.key);
                if (t.key === 'analytics' && !analytics) loadAnalytics();
              }}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>

        {/* ══════════ GENERAL TAB ══════════ */}
        {tab === 'general' && (
          <div className="p-4 space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left Column */}
              <div className="space-y-4">
                <div>
                  <label className="block text-xs text-[var(--color-text-muted)] mb-1">Product Name *</label>
                  <input value={product.name} onChange={e => setProduct(p => ({ ...p, name: e.target.value }))} className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                </div>
                <div>
                  <label className="block text-xs text-[var(--color-text-muted)] mb-1">Description</label>
                  <textarea rows={3} value={product.description || ''} onChange={e => setProduct(p => ({ ...p, description: e.target.value }))} className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-[var(--color-text-muted)] mb-1">Merchant</label>
                    <select value={product.merchant_id ?? ''} onChange={e => setProduct(p => ({ ...p, merchant_id: e.target.value ? Number(e.target.value) : null }))} className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg">
                      <option value="">All Merchants</option>
                      {merchants.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-[var(--color-text-muted)] mb-1">Lifecycle Status</label>
                    <select value={product.lifecycle_status || 'active'} onChange={e => setProduct(p => ({ ...p, lifecycle_status: e.target.value }))} className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg">
                      {LIFECYCLE_STATUSES.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
                    </select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-[var(--color-text-muted)] mb-1">Min Term (months)</label>
                    <input type="number" value={product.min_term_months} onChange={e => setProduct(p => ({ ...p, min_term_months: Number(e.target.value) }))} className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                  </div>
                  <div>
                    <label className="block text-xs text-[var(--color-text-muted)] mb-1">Max Term (months)</label>
                    <input type="number" value={product.max_term_months} onChange={e => setProduct(p => ({ ...p, max_term_months: Number(e.target.value) }))} className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-[var(--color-text-muted)] mb-1">Min Amount (TTD)</label>
                    <input type="number" value={product.min_amount} onChange={e => setProduct(p => ({ ...p, min_amount: Number(e.target.value) }))} className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                  </div>
                  <div>
                    <label className="block text-xs text-[var(--color-text-muted)] mb-1">Max Amount (TTD)</label>
                    <input type="number" value={product.max_amount} onChange={e => setProduct(p => ({ ...p, max_amount: Number(e.target.value) }))} className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-[var(--color-text-muted)] mb-1">Base Interest Rate (%)</label>
                    <input type="number" step="0.01" value={product.interest_rate ?? ''} onChange={e => setProduct(p => ({ ...p, interest_rate: e.target.value ? Number(e.target.value) : null }))} placeholder="e.g. 12.5" className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                  </div>
                  <div>
                    <label className="block text-xs text-[var(--color-text-muted)] mb-1">Regulatory Code</label>
                    <input value={product.regulatory_code || ''} onChange={e => setProduct(p => ({ ...p, regulatory_code: e.target.value }))} placeholder="e.g. CBTT-HP-001" className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                  </div>
                </div>
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={product.is_active} onChange={e => setProduct(p => ({ ...p, is_active: e.target.checked }))} />
                  <span className="text-sm">Active</span>
                </label>
              </div>

              {/* Right Column: Score Ranges + Channels + Segments */}
              <div className="space-y-4">
                {/* Score Ranges */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-semibold text-sm">Score Ranges</h3>
                    <Button size="sm" onClick={async () => {
                      if (isNew) { setPendingScoreRanges(prev => [...prev, { ...newScoreRange }]); setNewScoreRange({ min_score: 300, max_score: 850 }); }
                      else { await adminApi.createScoreRange(product.id, newScoreRange); setNewScoreRange({ min_score: 300, max_score: 850 }); await load(); }
                    }}><Plus size={14} className="mr-1" /> Add</Button>
                  </div>
                  <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead><tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]"><th className="px-3 py-2 text-left">Min</th><th className="px-3 py-2 text-left">Max</th><th className="px-3 py-2 text-left w-16"></th></tr></thead>
                      <tbody>
                        {product.score_ranges.map(sr => (
                          <tr key={sr.id} className="border-b border-[var(--color-border)]">
                            <td className="px-3 py-2">{sr.min_score}</td><td className="px-3 py-2">{sr.max_score}</td>
                            <td className="px-3 py-2"><button className="text-red-400 hover:text-red-300" onClick={async () => { await adminApi.deleteScoreRange(sr.id); await load(); }}>Del</button></td>
                          </tr>
                        ))}
                        {isNew && pendingScoreRanges.map((sr, idx) => (
                          <tr key={`p-${idx}`} className="border-b border-[var(--color-border)] bg-[var(--color-surface-hover)]">
                            <td className="px-3 py-2">{sr.min_score}</td><td className="px-3 py-2">{sr.max_score}</td>
                            <td className="px-3 py-2"><button className="text-red-400" onClick={() => setPendingScoreRanges(prev => prev.filter((_, i) => i !== idx))}>Rm</button></td>
                          </tr>
                        ))}
                        {product.score_ranges.length === 0 && (!isNew || pendingScoreRanges.length === 0) && (
                          <tr><td className="px-3 py-3 text-[var(--color-text-muted)]" colSpan={3}>No score ranges</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    <input type="number" placeholder="Min" value={newScoreRange.min_score} onChange={e => setNewScoreRange(s => ({ ...s, min_score: Number(e.target.value) }))} className="h-[36px] px-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm" />
                    <input type="number" placeholder="Max" value={newScoreRange.max_score} onChange={e => setNewScoreRange(s => ({ ...s, max_score: Number(e.target.value) }))} className="h-[36px] px-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm" />
                  </div>
                </div>

                {/* Channels */}
                <div>
                  <label className="block text-xs text-[var(--color-text-muted)] mb-2">
                    <Globe size={12} className="inline mr-1" />Distribution Channels
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {CHANNEL_OPTIONS.map(ch => (
                      <button key={ch} onClick={() => setProduct(p => ({ ...p, channels: toggleArrayItem(p.channels || [], ch) }))}
                        className={`px-3 py-1 rounded-full text-xs border transition-colors ${
                          (product.channels || []).includes(ch) ? 'border-blue-500 bg-blue-500/20 text-blue-400' : 'border-[var(--color-border)] text-[var(--color-text-muted)]'
                        }`}>{ch}</button>
                    ))}
                  </div>
                </div>

                {/* Target Segments */}
                <div>
                  <label className="block text-xs text-[var(--color-text-muted)] mb-2">
                    <Target size={12} className="inline mr-1" />Target Segments
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {SEGMENT_OPTIONS.map(seg => (
                      <button key={seg} onClick={() => setProduct(p => ({ ...p, target_segments: toggleArrayItem(p.target_segments || [], seg) }))}
                        className={`px-3 py-1 rounded-full text-xs border transition-colors ${
                          (product.target_segments || []).includes(seg) ? 'border-purple-500 bg-purple-500/20 text-purple-400' : 'border-[var(--color-border)] text-[var(--color-text-muted)]'
                        }`}>{seg}</button>
                    ))}
                  </div>
                </div>

                {/* Internal Notes */}
                <div>
                  <label className="block text-xs text-[var(--color-text-muted)] mb-1">Internal Notes</label>
                  <textarea rows={2} value={product.internal_notes || ''} onChange={e => setProduct(p => ({ ...p, internal_notes: e.target.value }))} placeholder="Internal notes visible only to admins..." className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm" />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ══════════ FEES TAB ══════════ */}
        {tab === 'fees' && (
          <div className="p-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Repayment Scheme</label>
                <select value={product.repayment_scheme} onChange={e => setProduct(p => ({ ...p, repayment_scheme: e.target.value }))} className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg">
                  {REPAYMENT_SCHEMES.map(rs => <option key={rs} value={rs}>{rs}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Grace Period (days)</label>
                <input type="number" value={product.grace_period_days} onChange={e => setProduct(p => ({ ...p, grace_period_days: Number(e.target.value) }))} className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Base Interest Rate (%)</label>
                <input type="number" step="0.01" value={product.interest_rate ?? ''} onChange={e => setProduct(p => ({ ...p, interest_rate: e.target.value ? Number(e.target.value) : null }))} className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
              </div>
            </div>

            <h3 className="font-semibold text-sm mt-4">Fee Schedule</h3>
            <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                  <th className="px-3 py-2 text-left">Type</th><th className="px-3 py-2 text-left">Base</th>
                  <th className="px-3 py-2 text-left">Amount</th><th className="px-3 py-2 text-left">Available</th>
                  <th className="px-3 py-2 text-left w-20"></th>
                </tr></thead>
                <tbody>
                  {product.fees.map(fee => (
                    <tr key={fee.id} className="border-b border-[var(--color-border)]">
                      <td className="px-3 py-2">{fee.fee_type}</td><td className="px-3 py-2">{fee.fee_base}</td>
                      <td className="px-3 py-2">{fee.fee_amount}</td><td className="px-3 py-2">{fee.is_available ? 'Yes' : 'No'}</td>
                      <td className="px-3 py-2"><button className="text-red-400 hover:text-red-300 inline-flex items-center gap-1" onClick={async () => { await adminApi.deleteFee(fee.id); await load(); }}><Trash2 size={14} /></button></td>
                    </tr>
                  ))}
                  {isNew && pendingFees.map((fee, idx) => (
                    <tr key={`pf-${idx}`} className="border-b border-[var(--color-border)] bg-[var(--color-surface-hover)]">
                      <td className="px-3 py-2">{fee.fee_type}</td><td className="px-3 py-2">{fee.fee_base}</td>
                      <td className="px-3 py-2">{fee.fee_amount}</td><td className="px-3 py-2">{fee.is_available ? 'Yes' : 'No'}</td>
                      <td className="px-3 py-2"><button className="text-red-400" onClick={() => setPendingFees(prev => prev.filter((_, i) => i !== idx))}><Trash2 size={14} /></button></td>
                    </tr>
                  ))}
                  {product.fees.length === 0 && (!isNew || pendingFees.length === 0) && (
                    <tr><td colSpan={5} className="px-3 py-3 text-[var(--color-text-muted)]">No fees configured</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
              <select value={newFee.fee_type} onChange={e => setNewFee(f => ({ ...f, fee_type: e.target.value }))} className="h-[38px] px-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm">
                {FEE_TYPES.map(ft => <option key={ft} value={ft}>{ft}</option>)}
              </select>
              <select value={newFee.fee_base} onChange={e => setNewFee(f => ({ ...f, fee_base: e.target.value }))} className="h-[38px] px-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm">
                {FEE_BASES.map(fb => <option key={fb} value={fb}>{fb}</option>)}
              </select>
              <input type="number" value={newFee.fee_amount} onChange={e => setNewFee(f => ({ ...f, fee_amount: Number(e.target.value) }))} className="h-[38px] px-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm" />
              <label className="inline-flex items-center gap-2 px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm">
                <input type="checkbox" checked={newFee.is_available} onChange={e => setNewFee(f => ({ ...f, is_available: e.target.checked }))} /><span>Available</span>
              </label>
              <Button onClick={async () => {
                if (isNew) { setPendingFees(prev => [...prev, { ...newFee }]); setNewFee({ fee_type: 'admin_fee_pct', fee_base: 'purchase_amount', fee_amount: 0, is_available: true }); }
                else { await adminApi.createFee(product.id, newFee); setNewFee({ fee_type: 'admin_fee_pct', fee_base: 'purchase_amount', fee_amount: 0, is_available: true }); await load(); }
              }}><Plus size={14} className="mr-1" /> Add Fee</Button>
            </div>
          </div>
        )}

        {/* ══════════ RISK PRICING TAB ══════════ */}
        {tab === 'pricing' && (
          <div className="p-4 space-y-4">
            <div className="flex items-start gap-3 p-3 rounded-lg bg-blue-500/5 border border-blue-500/20">
              <Zap size={16} className="text-blue-400 mt-0.5" />
              <div className="text-xs text-[var(--color-text-muted)]">
                <strong className="text-[var(--color-text)]">Risk-Based Pricing</strong> — Define interest rate tiers based on credit score bands.
                Each tier can have its own interest rate, maximum LTV ratio, and DTI limit.
                Applicants are automatically assigned to the best matching tier based on their credit score.
              </div>
            </div>

            <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                  <th className="px-3 py-2 text-left">Tier Name</th>
                  <th className="px-3 py-2 text-left">Score Range</th>
                  <th className="px-3 py-2 text-left">Interest Rate</th>
                  <th className="px-3 py-2 text-left">Max LTV %</th>
                  <th className="px-3 py-2 text-left">Max DTI %</th>
                  <th className="px-3 py-2 text-left">Active</th>
                  <th className="px-3 py-2 text-left w-16"></th>
                </tr></thead>
                <tbody>
                  {(product.rate_tiers || []).map(rt => (
                    <tr key={rt.id} className="border-b border-[var(--color-border)]">
                      <td className="px-3 py-2 font-medium">{rt.tier_name}</td>
                      <td className="px-3 py-2">{rt.min_score} – {rt.max_score}</td>
                      <td className="px-3 py-2 text-green-400">{rt.interest_rate}%</td>
                      <td className="px-3 py-2">{rt.max_ltv_pct != null ? `${rt.max_ltv_pct}%` : '—'}</td>
                      <td className="px-3 py-2">{rt.max_dti_pct != null ? `${rt.max_dti_pct}%` : '—'}</td>
                      <td className="px-3 py-2">{rt.is_active ? <CheckCircle2 size={14} className="text-green-400" /> : <span className="text-[var(--color-text-muted)]">No</span>}</td>
                      <td className="px-3 py-2"><button className="text-red-400 hover:text-red-300" onClick={async () => { await adminApi.deleteRateTier(rt.id); await load(); }}><Trash2 size={14} /></button></td>
                    </tr>
                  ))}
                  {isNew && pendingRateTiers.map((rt, idx) => (
                    <tr key={`prt-${idx}`} className="border-b border-[var(--color-border)] bg-[var(--color-surface-hover)]">
                      <td className="px-3 py-2 font-medium">{rt.tier_name}</td>
                      <td className="px-3 py-2">{rt.min_score} – {rt.max_score}</td>
                      <td className="px-3 py-2 text-green-400">{rt.interest_rate}%</td>
                      <td className="px-3 py-2">{rt.max_ltv_pct != null ? `${rt.max_ltv_pct}%` : '—'}</td>
                      <td className="px-3 py-2">{rt.max_dti_pct != null ? `${rt.max_dti_pct}%` : '—'}</td>
                      <td className="px-3 py-2">{rt.is_active ? 'Yes' : 'No'}</td>
                      <td className="px-3 py-2"><button className="text-red-400" onClick={() => setPendingRateTiers(prev => prev.filter((_, i) => i !== idx))}><Trash2 size={14} /></button></td>
                    </tr>
                  ))}
                  {(product.rate_tiers || []).length === 0 && (!isNew || pendingRateTiers.length === 0) && (
                    <tr><td colSpan={7} className="px-3 py-4 text-center text-[var(--color-text-muted)]">No rate tiers. Add tiers to enable risk-based pricing.</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-7 gap-2">
              <input value={newTier.tier_name} onChange={e => setNewTier(t => ({ ...t, tier_name: e.target.value }))} placeholder="Tier name" className="h-[38px] px-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm" />
              <input type="number" value={newTier.min_score} onChange={e => setNewTier(t => ({ ...t, min_score: Number(e.target.value) }))} placeholder="Min score" className="h-[38px] px-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm" />
              <input type="number" value={newTier.max_score} onChange={e => setNewTier(t => ({ ...t, max_score: Number(e.target.value) }))} placeholder="Max score" className="h-[38px] px-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm" />
              <input type="number" step="0.01" value={newTier.interest_rate} onChange={e => setNewTier(t => ({ ...t, interest_rate: Number(e.target.value) }))} placeholder="Rate %" className="h-[38px] px-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm" />
              <input type="number" value={newTier.max_ltv_pct} onChange={e => setNewTier(t => ({ ...t, max_ltv_pct: e.target.value }))} placeholder="LTV %" className="h-[38px] px-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm" />
              <input type="number" value={newTier.max_dti_pct} onChange={e => setNewTier(t => ({ ...t, max_dti_pct: e.target.value }))} placeholder="DTI %" className="h-[38px] px-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm" />
              <Button onClick={async () => {
                const tierData = {
                  tier_name: newTier.tier_name, min_score: newTier.min_score, max_score: newTier.max_score,
                  interest_rate: newTier.interest_rate,
                  max_ltv_pct: newTier.max_ltv_pct ? Number(newTier.max_ltv_pct) : null,
                  max_dti_pct: newTier.max_dti_pct ? Number(newTier.max_dti_pct) : null,
                  is_active: true,
                };
                if (isNew) {
                  setPendingRateTiers(prev => [...prev, tierData]);
                } else {
                  await adminApi.createRateTier(product.id, {
                    ...tierData,
                    max_ltv_pct: tierData.max_ltv_pct ?? undefined,
                    max_dti_pct: tierData.max_dti_pct ?? undefined,
                  });
                  await load();
                }
                setNewTier({ tier_name: '', min_score: 0, max_score: 0, interest_rate: 0, max_ltv_pct: '', max_dti_pct: '', is_active: true });
              }}><Plus size={14} className="mr-1" /> Add</Button>
            </div>
          </div>
        )}

        {/* ══════════ ELIGIBILITY TAB ══════════ */}
        {tab === 'eligibility' && (
          <div className="p-4 space-y-6">
            <div className="flex items-start gap-3 p-3 rounded-lg bg-green-500/5 border border-green-500/20">
              <Shield size={16} className="text-green-400 mt-0.5" />
              <div className="text-xs text-[var(--color-text-muted)]">
                <strong className="text-[var(--color-text)]">Eligibility Criteria</strong> — Define who qualifies for this product.
                These criteria are checked during the application process in addition to score ranges and business rules.
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-4">
                <h3 className="font-semibold text-sm">Applicant Requirements</h3>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-[var(--color-text-muted)] mb-1">Min Age</label>
                    <input type="number" value={elig.min_age ?? ''} onChange={e => setElig({ min_age: e.target.value ? Number(e.target.value) : null })} placeholder="18" className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                  </div>
                  <div>
                    <label className="block text-xs text-[var(--color-text-muted)] mb-1">Max Age</label>
                    <input type="number" value={elig.max_age ?? ''} onChange={e => setElig({ max_age: e.target.value ? Number(e.target.value) : null })} placeholder="65" className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-[var(--color-text-muted)] mb-1">Min Monthly Income (TTD)</label>
                    <input type="number" value={elig.min_income ?? ''} onChange={e => setElig({ min_income: e.target.value ? Number(e.target.value) : null })} placeholder="3000" className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                  </div>
                  <div>
                    <label className="block text-xs text-[var(--color-text-muted)] mb-1">Max DTI Ratio (%)</label>
                    <input type="number" value={elig.max_dti ?? ''} onChange={e => setElig({ max_dti: e.target.value ? Number(e.target.value) : null })} placeholder="50" className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-[var(--color-text-muted)] mb-1">Min Employment Duration (months)</label>
                  <input type="number" value={elig.min_employment_months ?? ''} onChange={e => setElig({ min_employment_months: e.target.value ? Number(e.target.value) : null })} placeholder="6" className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                </div>
                <div className="space-y-2">
                  <label className="flex items-center gap-2"><input type="checkbox" checked={!!elig.citizenship_required} onChange={e => setElig({ citizenship_required: e.target.checked })} /><span className="text-sm">Citizenship Required</span></label>
                  <label className="flex items-center gap-2"><input type="checkbox" checked={!!elig.existing_customer_only} onChange={e => setElig({ existing_customer_only: e.target.checked })} /><span className="text-sm">Existing Customers Only</span></label>
                </div>
              </div>

              <div className="space-y-4">
                <h3 className="font-semibold text-sm">Employment Types</h3>
                <div className="flex flex-wrap gap-2">
                  {EMPLOYMENT_TYPES.map(et => (
                    <button key={et} onClick={() => setElig({ employment_types: toggleArrayItem(elig.employment_types, et) })}
                      className={`px-3 py-1 rounded-full text-xs border transition-colors ${
                        (elig.employment_types || []).includes(et) ? 'border-green-500 bg-green-500/20 text-green-400' : 'border-[var(--color-border)] text-[var(--color-text-muted)]'
                      }`}>{et}</button>
                  ))}
                </div>

                <h3 className="font-semibold text-sm mt-4">Required Documents</h3>
                <div className="flex flex-wrap gap-2">
                  {DOCUMENT_OPTIONS.map(doc => (
                    <button key={doc} onClick={() => setElig({ required_documents: toggleArrayItem(elig.required_documents, doc) })}
                      className={`px-3 py-1 rounded-full text-xs border transition-colors ${
                        (elig.required_documents || []).includes(doc) ? 'border-blue-500 bg-blue-500/20 text-blue-400' : 'border-[var(--color-border)] text-[var(--color-text-muted)]'
                      }`}>{doc}</button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ══════════ ANALYTICS TAB ══════════ */}
        {tab === 'analytics' && !isNew && (
          <div className="p-4 space-y-6">
            {analyticsLoading && <div className="text-[var(--color-text-muted)]">Loading analytics...</div>}
            {analytics && (
              <>
                {/* Health Score */}
                <div className="flex items-start gap-4">
                  <div className={`w-20 h-20 rounded-2xl flex items-center justify-center text-2xl font-bold ${
                    analytics.health.score >= 80 ? 'bg-green-500/20 text-green-400' :
                    analytics.health.score >= 60 ? 'bg-yellow-500/20 text-yellow-400' :
                    analytics.health.score >= 40 ? 'bg-orange-500/20 text-orange-400' :
                    'bg-red-500/20 text-red-400'
                  }`}>
                    {analytics.health.score}
                  </div>
                  <div>
                    <h3 className="font-semibold">Product Health Score</h3>
                    <p className="text-sm text-[var(--color-text-muted)] capitalize">{analytics.health.status.replace('_', ' ')}</p>
                    <div className="flex gap-4 mt-2">
                      {analytics.health.factors.map((f, i) => (
                        <div key={i} className="text-xs">
                          <span className="text-[var(--color-text-muted)]">{f.name}:</span>{' '}
                          <span className={f.score >= 70 ? 'text-green-400' : f.score >= 40 ? 'text-yellow-400' : 'text-red-400'}>{f.score}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* KPI Cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {[
                    { label: 'Total Applications', value: analytics.metrics.total_applications, icon: <Activity size={14} /> },
                    { label: 'Last 30 Days', value: analytics.metrics.recent_applications_30d, icon: <TrendingUp size={14} /> },
                    { label: 'Approval Rate', value: `${analytics.metrics.approval_rate}%`, icon: <CheckCircle2 size={14} /> },
                    { label: 'Avg Loan', value: `TTD ${analytics.metrics.avg_loan_amount.toLocaleString()}`, icon: <BarChart3 size={14} /> },
                  ].map((kpi, i) => (
                    <div key={i} className="p-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]">
                      <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1">{kpi.icon} {kpi.label}</div>
                      <div className="text-lg font-semibold">{kpi.value}</div>
                    </div>
                  ))}
                </div>

                {/* Volume Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="p-4 rounded-lg border border-[var(--color-border)]">
                    <div className="text-xs text-[var(--color-text-muted)] mb-1">Total Disbursed</div>
                    <div className="text-xl font-semibold">TTD {analytics.metrics.total_disbursed_volume.toLocaleString()}</div>
                  </div>
                  <div className="p-4 rounded-lg border border-[var(--color-border)]">
                    <div className="text-xs text-[var(--color-text-muted)] mb-1">Total Collected</div>
                    <div className="text-xl font-semibold">TTD {analytics.metrics.total_collected.toLocaleString()}</div>
                  </div>
                </div>

                {/* Monthly Trend */}
                <div>
                  <h3 className="font-semibold text-sm mb-3">Monthly Application Trend</h3>
                  <div className="flex items-end gap-1 h-32">
                    {analytics.metrics.monthly_trend.map((m, i) => {
                      const max = Math.max(...analytics.metrics.monthly_trend.map(t => t.applications), 1);
                      const h = Math.max(4, (m.applications / max) * 100);
                      return (
                        <div key={i} className="flex-1 flex flex-col items-center gap-1">
                          <span className="text-[10px] text-[var(--color-text-muted)]">{m.applications}</span>
                          <div className="w-full rounded-t bg-blue-500/40" style={{ height: `${h}%` }} />
                          <span className="text-[10px] text-[var(--color-text-muted)]">{m.month.slice(0, 3)}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Status Breakdown */}
                <div>
                  <h3 className="font-semibold text-sm mb-3">Status Breakdown</h3>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(analytics.metrics.status_breakdown).map(([status, count]) => (
                      <div key={status} className="px-3 py-1.5 rounded-lg border border-[var(--color-border)] text-xs">
                        <span className="text-[var(--color-text-muted)]">{status}:</span> <strong>{count}</strong>
                      </div>
                    ))}
                  </div>
                </div>

                <Button variant="outline" size="sm" onClick={loadAnalytics}>
                  <RefreshCcw size={14} className="mr-1" /> Refresh Analytics
                </Button>
              </>
            )}
          </div>
        )}

        {/* ══════════ SIMULATOR TAB ══════════ */}
        {tab === 'simulator' && !isNew && (
          <div className="p-4 space-y-4">
            <div className="flex items-start gap-3 p-3 rounded-lg bg-purple-500/5 border border-purple-500/20">
              <Beaker size={16} className="text-purple-400 mt-0.5" />
              <div className="text-xs text-[var(--color-text-muted)]">
                <strong className="text-[var(--color-text)]">What-If Simulator</strong> — Enter proposed parameter changes below
                and AI will analyze the projected impact on volume, approval rates, and revenue.
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {[
                { key: 'min_amount', label: 'New Min Amount', current: product.min_amount },
                { key: 'max_amount', label: 'New Max Amount', current: product.max_amount },
                { key: 'min_term_months', label: 'New Min Term', current: product.min_term_months },
                { key: 'max_term_months', label: 'New Max Term', current: product.max_term_months },
                { key: 'grace_period_days', label: 'New Grace Period', current: product.grace_period_days },
                { key: 'interest_rate', label: 'New Interest Rate %', current: product.interest_rate || 0 },
              ].map(field => (
                <div key={field.key}>
                  <label className="block text-xs text-[var(--color-text-muted)] mb-1">{field.label} (current: {field.current})</label>
                  <input
                    type="number"
                    value={simChanges[field.key] || ''}
                    onChange={e => setSimChanges(prev => ({ ...prev, [field.key]: e.target.value }))}
                    placeholder={String(field.current)}
                    className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm"
                  />
                </div>
              ))}
            </div>

            <Button onClick={runSimulation} isLoading={simLoading}>
              <Beaker size={14} className="mr-1" /> Run Simulation
            </Button>

            {simResult?.analysis && typeof simResult.analysis === 'object' && (
              <div className="space-y-3 p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]">
                <h3 className="font-semibold text-sm">Simulation Results</h3>
                <p className="text-sm">{simResult.analysis.impact_summary}</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="text-center p-2 rounded bg-[var(--color-surface-hover)]">
                    <div className="text-xs text-[var(--color-text-muted)]">Risk Level</div>
                    <div className={`font-semibold text-sm ${
                      simResult.analysis.risk_level === 'low' ? 'text-green-400' :
                      simResult.analysis.risk_level === 'medium' ? 'text-yellow-400' : 'text-red-400'
                    }`}>{simResult.analysis.risk_level}</div>
                  </div>
                  <div className="text-center p-2 rounded bg-[var(--color-surface-hover)]">
                    <div className="text-xs text-[var(--color-text-muted)]">Volume Change</div>
                    <div className={`font-semibold text-sm ${simResult.analysis.projected_volume_change_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {simResult.analysis.projected_volume_change_pct >= 0 ? '+' : ''}{simResult.analysis.projected_volume_change_pct}%
                    </div>
                  </div>
                  <div className="text-center p-2 rounded bg-[var(--color-surface-hover)]">
                    <div className="text-xs text-[var(--color-text-muted)]">Approval Impact</div>
                    <div className={`font-semibold text-sm ${(simResult.analysis.projected_approval_rate_change_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {(simResult.analysis.projected_approval_rate_change_pct || 0) >= 0 ? '+' : ''}{simResult.analysis.projected_approval_rate_change_pct || 0}%
                    </div>
                  </div>
                  <div className="text-center p-2 rounded bg-[var(--color-surface-hover)]">
                    <div className="text-xs text-[var(--color-text-muted)]">Revenue Impact</div>
                    <div className={`font-semibold text-sm ${
                      simResult.analysis.projected_revenue_impact === 'positive' ? 'text-green-400' :
                      simResult.analysis.projected_revenue_impact === 'neutral' ? 'text-yellow-400' : 'text-red-400'
                    }`}>{simResult.analysis.projected_revenue_impact}</div>
                  </div>
                </div>
                {simResult.analysis.recommendations?.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-[var(--color-text-muted)] mb-1">Recommendations</h4>
                    <ul className="space-y-1">
                      {simResult.analysis.recommendations.map((r: string, i: number) => (
                        <li key={i} className="text-sm flex gap-2"><ChevronRight size={14} className="text-blue-400 shrink-0 mt-0.5" /> {r}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {simResult.analysis.warnings?.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-orange-400 mb-1">Warnings</h4>
                    <ul className="space-y-1">
                      {simResult.analysis.warnings.map((w: string, i: number) => (
                        <li key={i} className="text-sm flex gap-2"><AlertTriangle size={14} className="text-orange-400 shrink-0 mt-0.5" /> {w}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="text-xs text-[var(--color-text-muted)]">Confidence: {simResult.analysis.confidence}</div>
              </div>
            )}
          </div>
        )}

        {/* ══════════ AI ADVISOR TAB ══════════ */}
        {tab === 'advisor' && (
          <div className="p-4 flex flex-col" style={{ minHeight: '480px' }}>
            <div className="flex items-start gap-3 p-3 rounded-lg bg-purple-500/5 border border-purple-500/20 mb-4">
              <Brain size={16} className="text-purple-400 mt-0.5" />
              <div className="text-xs text-[var(--color-text-muted)]">
                <strong className="text-[var(--color-text)]">AI Product Advisor</strong> — Ask questions about product design,
                pricing strategy, fee optimization, market positioning, regulatory compliance, or portfolio management.
                {!isNew && ' The advisor has access to this product\'s performance data and configuration.'}
              </div>
            </div>

            {/* Quick prompts */}
            {chatMessages.length === 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-4">
                {[
                  'How should I optimize the fee structure for this product?',
                  'What interest rate tiers would you recommend?',
                  'Is this product at risk of cannibalizing others in our portfolio?',
                  'What eligibility criteria should I set to balance risk and volume?',
                  'How does this product compare to market standards in Trinidad?',
                  'What changes would improve the health score of this product?',
                ].map((prompt, i) => (
                  <button key={i} onClick={() => { setChatInput(prompt); }}
                    className="text-left text-xs p-2 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors text-[var(--color-text-muted)]">
                    {prompt}
                  </button>
                ))}
              </div>
            )}

            {/* Chat messages */}
            <div className="flex-1 overflow-y-auto space-y-3 mb-4 max-h-[400px]">
              {chatMessages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                    msg.role === 'user' ? 'bg-blue-500/20 text-blue-100' : 'bg-[var(--color-surface-hover)]'
                  }`}>
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  </div>
                </div>
              ))}
              {chatLoading && (
                <div className="flex justify-start">
                  <div className="bg-[var(--color-surface-hover)] rounded-lg px-3 py-2 text-sm text-[var(--color-text-muted)]">
                    Thinking...
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Chat input */}
            <div className="flex gap-2">
              <input
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendChat()}
                placeholder="Ask the AI advisor..."
                className="flex-1 px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm"
              />
              <Button onClick={sendChat} disabled={chatLoading || !chatInput.trim()}>
                <Send size={14} />
              </Button>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="border-t border-[var(--color-border)] p-4 flex items-center justify-between">
          <Button variant="ghost" onClick={() => navigate('/backoffice/products')}>Cancel &amp; Close</Button>
          <Button onClick={saveProduct} isLoading={saving}>Save Product</Button>
        </div>
      </Card>
    </div>
  );
}
