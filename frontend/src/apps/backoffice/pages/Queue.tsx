import { useEffect, useState, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { RefreshCw, Search, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { getStatusBadge } from '../../../components/ui/Badge';
import { underwriterApi } from '../../../api/endpoints';

interface Application {
  id: number;
  reference_number: string;
  applicant_id: number;
  applicant_name: string | null;
  amount_requested: number;
  term_months: number;
  purpose: string;
  status: string;
  submitted_at: string | null;
  created_at: string;
  assigned_underwriter_id: number | null;
}

type SortKey = 'reference_number' | 'applicant_name' | 'amount_requested' | 'term_months' | 'purpose' | 'status' | 'created_at';
type SortDir = 'asc' | 'desc';

const STATUS_FILTERS = [
  { value: 'all', label: 'All Statuses' },
  { value: '', label: 'All Active' },
  { value: 'draft', label: 'Draft' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'under_review', label: 'Under Review' },
  { value: 'credit_check', label: 'Credit Check' },
  { value: 'decision_pending', label: 'Decision Pending' },
  { value: 'awaiting_documents', label: 'Awaiting Documents' },
  { value: 'approved', label: 'Approved' },
  { value: 'declined', label: 'Declined' },
  { value: 'offer_sent', label: 'Offer Sent' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'counter_proposed', label: 'Counter Proposed' },
  { value: 'disbursed', label: 'Disbursed' },
  { value: 'rejected_by_applicant', label: 'Rejected by Applicant' },
  { value: 'cancelled', label: 'Cancelled' },
];

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'reference_number', label: 'Reference' },
  { key: 'applicant_name', label: 'Applicant' },
  { key: 'amount_requested', label: 'Amount' },
  { key: 'term_months', label: 'Term' },
  { key: 'status', label: 'Status' },
  { key: 'created_at', label: 'Date' },
];

const INITIAL_STATUSES = ['all', '', 'draft', 'submitted', 'under_review', 'credit_check', 'decision_pending', 'awaiting_documents', 'approved', 'declined', 'offer_sent', 'accepted', 'counter_proposed', 'disbursed', 'rejected_by_applicant', 'cancelled'];

export default function Applications() {
  const [searchParams] = useSearchParams();
  const urlStatus = searchParams.get('status_filter');
  const initialFilter = urlStatus && INITIAL_STATUSES.includes(urlStatus) ? urlStatus : 'all';
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState(initialFilter);
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('created_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  // Sync filter from URL when navigating with status_filter (e.g. from dashboard tile)
  useEffect(() => {
    if (urlStatus && INITIAL_STATUSES.includes(urlStatus)) {
      setFilter(urlStatus);
    }
  }, [urlStatus]);

  const loadApplications = () => {
    setLoading(true);
    const params = filter === 'all' ? 'all' : filter || undefined;
    underwriterApi.getQueue(params)
      .then((res) => setApplications(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadApplications(); }, [filter]);

  const handleAssign = async (id: number) => {
    await underwriterApi.assign(id);
    loadApplications();
  };

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(key === 'created_at' || key === 'amount_requested' ? 'desc' : 'asc');
    }
  };

  const sortIcon = (key: SortKey) => {
    if (sortKey !== key) return <ArrowUpDown size={12} className="ml-1 opacity-30" />;
    return sortDir === 'asc'
      ? <ArrowUp size={12} className="ml-1 text-[var(--color-primary)]" />
      : <ArrowDown size={12} className="ml-1 text-[var(--color-primary)]" />;
  };

  /** Filtered + sorted applications (client-side). */
  const displayed = useMemo(() => {
    const q = search.trim().toLowerCase();

    // Filter by search query
    let list = applications;
    if (q) {
      list = list.filter((app) => {
        const name = (app.applicant_name || '').toLowerCase();
        const ref = app.reference_number.toLowerCase();
        const idStr = String(app.id);
        return name.includes(q) || ref.includes(q) || idStr.includes(q);
      });
    }

    // Sort
    const sorted = [...list].sort((a, b) => {
      let aVal: string | number = '';
      let bVal: string | number = '';

      switch (sortKey) {
        case 'reference_number':
          aVal = a.reference_number;
          bVal = b.reference_number;
          break;
        case 'applicant_name':
          aVal = (a.applicant_name || '').toLowerCase();
          bVal = (b.applicant_name || '').toLowerCase();
          break;
        case 'amount_requested':
          aVal = a.amount_requested;
          bVal = b.amount_requested;
          break;
        case 'term_months':
          aVal = a.term_months;
          bVal = b.term_months;
          break;
        case 'purpose':
          aVal = a.purpose;
          bVal = b.purpose;
          break;
        case 'status':
          aVal = a.status;
          bVal = b.status;
          break;
        case 'created_at':
          aVal = a.created_at || '';
          bVal = b.created_at || '';
          break;
      }

      if (aVal < bVal) return sortDir === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });

    return sorted;
  }, [applications, search, sortKey, sortDir]);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">Applications</h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            {displayed.length}{displayed.length !== applications.length ? ` of ${applications.length}` : ''} application{applications.length !== 1 ? 's' : ''}
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={loadApplications}>
          <RefreshCw size={14} className="mr-1" /> Refresh
        </Button>
      </div>

      {/* Search + filter bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 mb-4">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, reference or ID..."
            className="w-full pl-9 pr-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none"
          />
        </div>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none"
        >
          {STATUS_FILTERS.map((f) => (
            <option key={f.value} value={f.value}>{f.label}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <Card padding="none">
        {loading ? (
          <p className="text-center py-8 text-[var(--color-text-muted)]">Loading applications...</p>
        ) : displayed.length === 0 ? (
          <p className="text-center py-8 text-[var(--color-text-muted)]">
            {search ? 'No applications match your search' : 'No applications found'}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  {COLUMNS.map(({ key, label }) => (
                    <th
                      key={key}
                      onClick={() => handleSort(key)}
                      className="text-left py-3 px-4 text-[var(--color-text-muted)] font-medium text-xs uppercase tracking-wider cursor-pointer select-none hover:text-[var(--color-text)] transition-colors"
                    >
                      <span className="inline-flex items-center">
                        {label}
                        {sortIcon(key)}
                      </span>
                    </th>
                  ))}
                  <th className="text-left py-3 px-4 text-[var(--color-text-muted)] font-medium text-xs uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody>
                {displayed.map((app) => (
                  <tr key={app.id} className="border-b border-[var(--color-border)]/50 hover:bg-[var(--color-surface-hover)] transition-colors">
                    <td className="py-3 px-4 font-medium">
                      <Link to={`/backoffice/review/${app.id}`} className="text-[var(--color-primary)] hover:text-[var(--color-primary-light)] transition-colors">
                        {app.reference_number}
                      </Link>
                    </td>
                    <td className="py-3 px-4 text-[var(--color-text)]">
                      <Link to={`/backoffice/customers/${app.applicant_id}`} className="hover:text-[var(--color-primary)] transition-colors">
                        {app.applicant_name || '—'}
                      </Link>
                    </td>
                    <td className="py-3 px-4 text-[var(--color-text)] font-medium">TTD {app.amount_requested.toLocaleString()}</td>
                    <td className="py-3 px-4 text-[var(--color-text-muted)]">{app.term_months}m</td>
                    <td className="py-3 px-4">{getStatusBadge(app.status)}</td>
                    <td className="py-3 px-4 text-[var(--color-text-muted)]">
                      {new Date(app.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        <Link to={`/backoffice/review/${app.id}`}>
                          <Button size="sm" variant="outline">Review</Button>
                        </Link>
                        {!app.assigned_underwriter_id && app.status === 'submitted' && (
                          <Button size="sm" variant="ghost" onClick={() => handleAssign(app.id)}>
                            Assign
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
