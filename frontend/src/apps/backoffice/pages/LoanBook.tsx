import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { BookOpen, Search, Filter, ArrowUpDown, ChevronDown } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Badge, { getStatusBadge } from '../../../components/ui/Badge';
import { underwriterApi } from '../../../api/endpoints';

interface LoanEntry {
  id: number;
  reference_number: string;
  applicant_name: string;
  amount_requested: number;
  amount_approved: number | null;
  term_months: number;
  interest_rate: number | null;
  monthly_payment: number | null;
  status: string;
  risk_band: string | null;
  credit_score: number | null;
  disbursed_date: string | null;
  outstanding_balance: number | null;
  days_past_due: number;
  next_payment_date: string | null;
  purpose: string;
  created_at: string;
}

const STATUS_OPTIONS = [
  'all', 'draft', 'submitted', 'under_review', 'credit_check', 'decision_pending',
  'approved', 'declined', 'disbursed', 'accepted', 'counter_proposed', 'cancelled',
];

const RISK_OPTIONS = ['all', 'A', 'B', 'C', 'D', 'E'];

export default function LoanBook() {
  const [loans, setLoans] = useState<LoanEntry[]>([]);
  const [filtered, setFiltered] = useState<LoanEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [searchParams] = useSearchParams();
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || 'all');
  const [riskFilter, setRiskFilter] = useState('all');
  const [sortField, setSortField] = useState<string>('created_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const navigate = useNavigate();

  useEffect(() => {
    loadLoans();
  }, []);

  useEffect(() => {
    const s = searchParams.get('status');
    if (s) setStatusFilter(s);
  }, [searchParams]);

  useEffect(() => {
    applyFilters();
  }, [loans, search, statusFilter, riskFilter, sortField, sortDir]);

  const loadLoans = async () => {
    try {
      const res = await underwriterApi.getLoanBook();
      setLoans(res.data);
    } catch { /* ignore */ }
    setLoading(false);
  };

  const applyFilters = () => {
    let result = [...loans];
    if (statusFilter !== 'all') {
      result = result.filter(l => l.status === statusFilter);
    }
    if (riskFilter !== 'all') {
      result = result.filter(l => l.risk_band === riskFilter);
    }
    if (search) {
      const s = search.toLowerCase();
      result = result.filter(l =>
        l.reference_number.toLowerCase().includes(s) ||
        l.applicant_name.toLowerCase().includes(s)
      );
    }
    // Sort
    result.sort((a, b) => {
      const aVal = (a as any)[sortField];
      const bVal = (b as any)[sortField];
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
      return sortDir === 'asc' ? cmp : -cmp;
    });
    setFiltered(result);
  };

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  const fmt = (val: number | null) => val != null ? `TTD ${val.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '—';

  const riskColor = (band: string | null) => {
    const colors: Record<string, string> = { A: 'text-emerald-400', B: 'text-cyan-400', C: 'text-amber-400', D: 'text-orange-400', E: 'text-red-400' };
    return colors[band || ''] || 'text-gray-400';
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-[var(--color-text-muted)]">Loading loan book...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-[var(--color-cyan)]/15 rounded-lg">
            <BookOpen className="text-[var(--color-cyan)]" size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Loan Book</h1>
            <p className="text-sm text-[var(--color-text-muted)]">{filtered.length} of {loans.length} loans</p>
          </div>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex-1 min-w-[200px] relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
            <input
              type="text"
              placeholder="Search by reference or name..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
            />
          </div>
          <div className="flex items-center space-x-2">
            <Filter size={14} className="text-[var(--color-text-muted)]" />
            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-sm text-[var(--color-text)]"
            >
              {STATUS_OPTIONS.map(s => (
                <option key={s} value={s}>{s === 'all' ? 'All Statuses' : s.replace(/_/g, ' ')}</option>
              ))}
            </select>
            <select
              value={riskFilter}
              onChange={e => setRiskFilter(e.target.value)}
              className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-sm text-[var(--color-text)]"
            >
              {RISK_OPTIONS.map(r => (
                <option key={r} value={r}>{r === 'all' ? 'All Risk Bands' : `Band ${r}`}</option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      {/* Table */}
      <Card padding="none">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                {[
                  { key: 'reference_number', label: 'Reference' },
                  { key: 'applicant_name', label: 'Applicant' },
                  { key: 'amount_requested', label: 'Requested' },
                  { key: 'amount_approved', label: 'Approved' },
                  { key: 'term_months', label: 'Term' },
                  { key: 'interest_rate', label: 'Rate' },
                  { key: 'status', label: 'Status' },
                  { key: 'risk_band', label: 'Risk' },
                  { key: 'credit_score', label: 'Score' },
                  { key: 'outstanding_balance', label: 'Outstanding' },
                  { key: 'days_past_due', label: 'DPD' },
                ].map(col => (
                  <th
                    key={col.key}
                    className="px-4 py-3 text-left cursor-pointer hover:text-[var(--color-text)] whitespace-nowrap"
                    onClick={() => handleSort(col.key)}
                  >
                    <div className="flex items-center space-x-1">
                      <span>{col.label}</span>
                      {sortField === col.key && (
                        <ArrowUpDown size={12} className="text-[var(--color-primary)]" />
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(loan => {
                const badge = getStatusBadge(loan.status);
                return (
                  <tr
                    key={loan.id}
                    className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] cursor-pointer transition-colors"
                    onClick={() => navigate(`/backoffice/review/${loan.id}`)}
                  >
                    <td className="px-4 py-3 font-mono text-xs text-[var(--color-primary)]">{loan.reference_number}</td>
                    <td className="px-4 py-3">{loan.applicant_name}</td>
                    <td className="px-4 py-3 whitespace-nowrap">{fmt(loan.amount_requested)}</td>
                    <td className="px-4 py-3 whitespace-nowrap">{fmt(loan.amount_approved)}</td>
                    <td className="px-4 py-3">{loan.term_months}mo</td>
                    <td className="px-4 py-3">{loan.interest_rate ? `${loan.interest_rate}%` : '—'}</td>
                    <td className="px-4 py-3"><Badge variant={badge.variant}>{badge.label}</Badge></td>
                    <td className={`px-4 py-3 font-bold ${riskColor(loan.risk_band)}`}>{loan.risk_band || '—'}</td>
                    <td className="px-4 py-3">{loan.credit_score || '—'}</td>
                    <td className="px-4 py-3 whitespace-nowrap">{fmt(loan.outstanding_balance)}</td>
                    <td className="px-4 py-3">
                      {loan.days_past_due > 0 ? (
                        <span className={`font-bold ${loan.days_past_due > 90 ? 'text-red-400' : loan.days_past_due > 30 ? 'text-amber-400' : 'text-yellow-400'}`}>
                          {loan.days_past_due}
                        </span>
                      ) : '—'}
                    </td>
                  </tr>
                );
              })}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={11} className="px-4 py-8 text-center text-[var(--color-text-muted)]">
                    No loans found matching your criteria
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
