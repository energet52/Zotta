import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, RefreshCcw, Search } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { adminApi } from '../../../api/endpoints';

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
};

export default function ProductManagement() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const navigate = useNavigate();

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

  useEffect(() => {
    loadProducts();
  }, []);

  const displayed = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return products;
    return products.filter((p) =>
      [p.name, p.description || '', p.merchant_name || '']
        .join(' ')
        .toLowerCase()
        .includes(q),
    );
  }, [products, search]);

  if (loading) {
    return <div className="text-[var(--color-text-muted)]">Loading products...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Credit Product Management</h1>
          <p className="text-sm text-[var(--color-text-muted)]">Manage product setup, tenures, fees, and score ranges</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={loadProducts}>
            <RefreshCcw size={14} className="mr-1" /> Refresh
          </Button>
          <Button onClick={() => navigate('/backoffice/products/new')}>
            <Plus size={14} className="mr-1" /> Add Product
          </Button>
        </div>
      </div>

      <Card>
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search products, descriptions, merchants..."
            className="w-full pl-9 pr-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm"
          />
        </div>
      </Card>

      <Card padding="none">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                <th className="px-4 py-3 text-left">Product Name</th>
                <th className="px-4 py-3 text-left">Product Description</th>
                <th className="px-4 py-3 text-left">Merchant Name</th>
                <th className="px-4 py-3 text-left">Min Term</th>
                <th className="px-4 py-3 text-left">Max Term</th>
                <th className="px-4 py-3 text-left">Min Amount, $</th>
                <th className="px-4 py-3 text-left">Max Amount, $</th>
                <th className="px-4 py-3 text-left">Deactivated</th>
              </tr>
            </thead>
            <tbody>
              {displayed.map((p) => (
                <tr
                  key={p.id}
                  onClick={() => navigate(`/backoffice/products/${p.id}`)}
                  className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] cursor-pointer"
                >
                  <td className="px-4 py-2">{p.name}</td>
                  <td className="px-4 py-2 text-[var(--color-text-muted)]">{p.description || '—'}</td>
                  <td className="px-4 py-2">{p.merchant_name || 'All Merchants'}</td>
                  <td className="px-4 py-2">{p.min_term_months}</td>
                  <td className="px-4 py-2">{p.max_term_months}</td>
                  <td className="px-4 py-2">{p.min_amount.toLocaleString()}</td>
                  <td className="px-4 py-2">{p.max_amount.toLocaleString()}</td>
                  <td className="px-4 py-2">{p.is_active ? 'No' : 'Yes'}</td>
                </tr>
              ))}
              {displayed.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-[var(--color-text-muted)]">
                    No products found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
