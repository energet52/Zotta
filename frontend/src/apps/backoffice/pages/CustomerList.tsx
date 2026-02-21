import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Users, ArrowRight } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Input from '../../../components/ui/Input';
import Badge from '../../../components/ui/Badge';
import { underwriterApi } from '../../../api/endpoints';

interface CustomerResult {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  role: string;
  is_active: boolean;
  profile?: {
    national_id?: string;
    employer_name?: string;
    monthly_income?: number;
    city?: string;
  };
}

export default function CustomerList() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<CustomerResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const res = await underwriterApi.searchCustomers(q.trim());
      setResults(res.data || []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') doSearch(query);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Users className="w-7 h-7 text-[var(--color-primary)]" />
            Customers
          </h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            Search customers to access the full Customer 360 view
          </p>
        </div>
      </div>

      {/* Search */}
      <Card>
        <div className="flex gap-3">
          <div className="flex-1">
            <Input
              placeholder="Search by name, email, phone, or national ID..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
            />
          </div>
          <button
            onClick={() => doSearch(query)}
            disabled={loading || !query.trim()}
            className="px-5 py-2 rounded-lg bg-[var(--color-primary)] text-white font-medium hover:opacity-90 transition disabled:opacity-50 flex items-center gap-2"
          >
            <Search className="w-4 h-4" />
            Search
          </button>
        </div>
      </Card>

      {/* Results */}
      {loading && (
        <div className="text-center py-12 text-[var(--color-text-muted)]">Searching...</div>
      )}

      {!loading && searched && results.length === 0 && (
        <Card>
          <div className="text-center py-8 text-[var(--color-text-muted)]">
            No customers found. Try a different search term.
          </div>
        </Card>
      )}

      {!loading && results.length > 0 && (
        <Card padding="none">
          <div className="overflow-x-auto max-w-full">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-left text-[var(--color-text-muted)]">
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Email</th>
                  <th className="px-4 py-3 font-medium">Phone</th>
                  <th className="px-4 py-3 font-medium">Employer</th>
                  <th className="px-4 py-3 font-medium">Location</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium" />
                </tr>
              </thead>
              <tbody>
                {results.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => navigate(`/backoffice/customers/${c.id}`)}
                    className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] cursor-pointer transition"
                  >
                    <td className="px-4 py-3 font-medium">
                      {c.first_name} {c.last_name}
                    </td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">{c.email}</td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">{c.phone || '—'}</td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">
                      {c.profile?.employer_name || '—'}
                    </td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">
                      {c.profile?.city || '—'}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={c.is_active ? 'success' : 'danger'}>
                        {c.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <ArrowRight className="w-4 h-4 text-[var(--color-text-muted)]" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
