import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Plus, RefreshCcw, Search, BarChart3, Brain,
  Activity, TrendingUp, ArrowRightLeft, Sparkles,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { adminApi } from '../../../api/endpoints';
import api from '../../../api/client';

type StrategyRef = { id: number; name: string; status: string };

type Product = {
  id: number;
  name: string;
  description?: string;
  merchant_id?: number | null;
  merchant_name?: string | null;
  min_term_months: number;
  max_term_months: number;
  min_amount: number;
  max_amount: number;
  is_active: boolean;
  lifecycle_status?: string;
  interest_rate?: number | null;
  decision_tree_id?: number | null;
  default_strategy_id?: number | null;
};

type PortfolioProduct = {
  id: number;
  name: string;
  applications: number;
  disbursed_volume: number;
  health_score: number;
  health_status: string;
};

type Portfolio = {
  total_products: number;
  total_applications: number;
  total_disbursed_volume: number;
  products: PortfolioProduct[];
};

export default function ProductManagement() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [portfolioLoading, setPortfolioLoading] = useState(false);
  const [showCompare, setShowCompare] = useState(false);
  const [compareIds, setCompareIds] = useState<number[]>([]);
  const [compareResult, setCompareResult] = useState<any>(null);
  const [comparing, setComparing] = useState(false);
  const [showAiGenerate, setShowAiGenerate] = useState(false);
  const [generatePrompt, setGeneratePrompt] = useState('');
  const [generating, setGenerating] = useState(false);
  const [strategies, setStrategies] = useState<StrategyRef[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    api.get('/strategies').then((res) => setStrategies(res.data || [])).catch(() => {});
  }, []);

  const strategyMap = useMemo(() => {
    const m = new Map<number, string>();
    strategies.forEach((s) => m.set(s.id, s.name));
    return m;
  }, [strategies]);

  const loadProducts = async () => {
    setLoading(true);
    try {
      const res = await adminApi.getProducts();
      setProducts(res.data || []);
    } catch {
      setProducts([]);
    } finally {
      setLoading(false);
    }
  };

  const loadPortfolio = async () => {
    setPortfolioLoading(true);
    try {
      const res = await adminApi.getPortfolioOverview();
      setPortfolio(res.data);
    } catch { /* ignore */ }
    finally { setPortfolioLoading(false); }
  };

  useEffect(() => { loadProducts(); loadPortfolio(); }, []);

  const displayed = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return products;
    return products.filter(p =>
      [p.name, p.description || '', p.merchant_name || ''].join(' ').toLowerCase().includes(q),
    );
  }, [products, search]);

  const healthMap = useMemo(() => {
    const m: Record<number, PortfolioProduct> = {};
    if (portfolio) portfolio.products.forEach(p => { m[p.id] = p; });
    return m;
  }, [portfolio]);

  const toggleCompare = (id: number) => {
    setCompareIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };

  const runCompare = async () => {
    if (compareIds.length < 2) return;
    setComparing(true);
    try {
      const res = await adminApi.productCompare({ product_ids: compareIds });
      setCompareResult(res.data);
    } catch { /* ignore */ }
    finally { setComparing(false); }
  };

  const aiGenerate = async () => {
    if (!generatePrompt.trim()) return;
    setGenerating(true);
    try {
      const res = await adminApi.productGenerate({ description: generatePrompt.trim() });
      if (res.data.product) {
        navigate('/backoffice/products/new', { state: { generated: res.data.product } });
      }
    } catch { /* ignore */ }
    finally { setGenerating(false); }
  };

  const lifecycleColor: Record<string, string> = {
    draft: 'bg-yellow-500/20 text-yellow-400',
    active: 'bg-green-500/20 text-green-400',
    sunset: 'bg-orange-500/20 text-orange-400',
    retired: 'bg-red-500/20 text-red-400',
  };

  const healthColor = (score: number) =>
    score >= 80 ? 'text-green-400' : score >= 60 ? 'text-yellow-400' : score >= 40 ? 'text-orange-400' : 'text-red-400';

  if (loading) {
    return <div className="text-[var(--color-text-muted)]">Loading products...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-bold">Credit Product Management</h1>
          <p className="text-sm text-[var(--color-text-muted)]">AI-powered product lifecycle, pricing, and portfolio management</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button variant="outline" size="sm" onClick={() => setShowCompare(!showCompare)}>
            <ArrowRightLeft size={14} className="mr-1" /> {showCompare ? 'Exit Compare' : 'Compare'}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setShowAiGenerate(!showAiGenerate)}>
            <Sparkles size={14} className="mr-1" /> AI Generate
          </Button>
          <Button variant="outline" size="sm" onClick={() => { loadProducts(); loadPortfolio(); }}>
            <RefreshCcw size={14} className="mr-1" /> Refresh
          </Button>
          <Button onClick={() => navigate('/backoffice/products/new')}>
            <Plus size={14} className="mr-1" /> Add Product
          </Button>
        </div>
      </div>

      {/* AI Product Generator */}
      {showAiGenerate && (
        <Card>
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400"><Sparkles size={20} /></div>
            <div className="flex-1">
              <h3 className="font-semibold text-sm mb-1">AI Product Generator</h3>
              <p className="text-xs text-[var(--color-text-muted)] mb-2">Describe the product you need and AI will design it from scratch</p>
              <div className="flex gap-2">
                <input value={generatePrompt} onChange={e => setGeneratePrompt(e.target.value)}
                  placeholder="e.g. A furniture hire-purchase product for middle-income families, up to TTD 50,000..."
                  className="flex-1 px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm"
                  onKeyDown={e => e.key === 'Enter' && aiGenerate()} />
                <Button onClick={aiGenerate} isLoading={generating} size="sm">
                  <Sparkles size={14} className="mr-1" /> Generate
                </Button>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Portfolio Overview */}
      {portfolio && !portfolioLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          <div className="p-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]">
            <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1"><BarChart3 size={14} /> Active Products</div>
            <div className="text-xl font-semibold">{portfolio.total_products}</div>
          </div>
          <div className="p-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]">
            <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1"><Activity size={14} /> Total Applications</div>
            <div className="text-xl font-semibold">{portfolio.total_applications.toLocaleString()}</div>
          </div>
          <div className="p-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]">
            <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1"><TrendingUp size={14} /> Total Disbursed</div>
            <div className="text-xl font-semibold">TTD {portfolio.total_disbursed_volume.toLocaleString()}</div>
          </div>
          <div className="p-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]">
            <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1"><Brain size={14} /> Avg Health Score</div>
            <div className="text-xl font-semibold">
              {portfolio.products.length > 0
                ? Math.round(portfolio.products.reduce((s, p) => s + p.health_score, 0) / portfolio.products.length)
                : 0}
            </div>
          </div>
        </div>
      )}

      {/* Search */}
      <Card>
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search products, descriptions, merchants..."
            className="w-full pl-9 pr-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm" />
        </div>
      </Card>

      {/* Compare toolbar */}
      {showCompare && (
        <div className="flex items-center gap-3 p-3 rounded-lg border border-blue-500/30 bg-blue-500/5">
          <ArrowRightLeft size={16} className="text-blue-400" />
          <span className="text-sm">Select 2+ products to compare. Selected: <strong>{compareIds.length}</strong></span>
          <Button size="sm" onClick={runCompare} disabled={compareIds.length < 2} isLoading={comparing}>
            Compare Selected
          </Button>
          {compareIds.length > 0 && (
            <Button size="sm" variant="ghost" onClick={() => { setCompareIds([]); setCompareResult(null); }}>Clear</Button>
          )}
        </div>
      )}

      {/* Compare result */}
      {compareResult?.analysis && (
        <Card>
          <h3 className="font-semibold text-sm mb-3">AI Comparison Analysis</h3>
          <p className="text-sm mb-3">{compareResult.analysis.summary}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-3">
            <div className="p-2 rounded bg-[var(--color-surface-hover)] text-center">
              <div className="text-xs text-[var(--color-text-muted)]">Best Product</div>
              <div className="text-sm font-semibold">{compareResult.analysis.winner}</div>
            </div>
            <div className="p-2 rounded bg-[var(--color-surface-hover)] text-center">
              <div className="text-xs text-[var(--color-text-muted)]">Cannibalization Risk</div>
              <div className={`text-sm font-semibold ${
                compareResult.analysis.cannibalization_risk === 'low' ? 'text-green-400' :
                compareResult.analysis.cannibalization_risk === 'medium' ? 'text-yellow-400' : 'text-red-400'
              }`}>{compareResult.analysis.cannibalization_risk}</div>
            </div>
            <div className="p-2 rounded bg-[var(--color-surface-hover)] text-center">
              <div className="text-xs text-[var(--color-text-muted)]">Products Compared</div>
              <div className="text-sm font-semibold">{compareResult.products?.length || 0}</div>
            </div>
          </div>
          {compareResult.analysis.recommendations?.length > 0 && (
            <div className="space-y-1">
              {compareResult.analysis.recommendations.map((r: string, i: number) => (
                <p key={i} className="text-xs text-[var(--color-text-muted)]">• {r}</p>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Product Table */}
      <Card padding="none">
        <div className="overflow-x-auto max-w-full">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                {showCompare && <th className="px-3 py-3 text-left w-10"></th>}
                <th className="px-4 py-3 text-left">Product</th>
                <th className="px-4 py-3 text-left">Merchant</th>
                <th className="px-4 py-3 text-left">Strategy</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Term Range</th>
                <th className="px-4 py-3 text-left">Amount Range (TTD)</th>
                <th className="px-4 py-3 text-left">Rate</th>
                <th className="px-4 py-3 text-left">Health</th>
                <th className="px-4 py-3 text-left">Apps</th>
                <th className="px-4 py-3 text-left">Volume</th>
              </tr>
            </thead>
            <tbody>
              {displayed.map(p => {
                const health = healthMap[p.id];
                return (
                  <tr key={p.id}
                    onClick={() => !showCompare && navigate(`/backoffice/products/${p.id}`)}
                    className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] cursor-pointer">
                    {showCompare && (
                      <td className="px-3 py-2" onClick={e => e.stopPropagation()}>
                        <input type="checkbox" checked={compareIds.includes(p.id)}
                          onChange={() => toggleCompare(p.id)} />
                      </td>
                    )}
                    <td className="px-4 py-2">
                      <div className="font-medium">{p.name}</div>
                      {p.description && <div className="text-xs text-[var(--color-text-muted)] truncate max-w-[200px]">{p.description}</div>}
                    </td>
                    <td className="px-4 py-2 text-[var(--color-text-muted)]">{p.merchant_name || 'All'}</td>
                    <td className="px-4 py-2">
                      {p.default_strategy_id ? (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500">
                          {strategyMap.get(p.default_strategy_id) || `#${p.default_strategy_id}`}
                        </span>
                      ) : (
                        <span className="text-xs text-[var(--color-text-muted)]">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${lifecycleColor[p.lifecycle_status || 'active']}`}>
                        {p.lifecycle_status || 'active'}
                      </span>
                    </td>
                    <td className="px-4 py-2">{p.min_term_months}–{p.max_term_months}mo</td>
                    <td className="px-4 py-2">{p.min_amount.toLocaleString()}–{p.max_amount.toLocaleString()}</td>
                    <td className="px-4 py-2">{p.interest_rate != null ? `${p.interest_rate}%` : '—'}</td>
                    <td className="px-4 py-2">
                      {health ? (
                        <span className={`font-semibold ${healthColor(health.health_score)}`}>{health.health_score}</span>
                      ) : (
                        <span className="text-[var(--color-text-muted)]">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2">{health?.applications?.toLocaleString() || '—'}</td>
                    <td className="px-4 py-2">{health?.disbursed_volume ? `${(health.disbursed_volume / 1000).toFixed(0)}k` : '—'}</td>
                  </tr>
                );
              })}
              {displayed.length === 0 && (
                <tr><td colSpan={showCompare ? 11 : 10} className="px-4 py-8 text-center text-[var(--color-text-muted)]">No products found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
