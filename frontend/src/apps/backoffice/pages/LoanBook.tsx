import { Fragment, useEffect, useState, useMemo } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { BookOpen, Search, ArrowUpDown, ArrowUp, ArrowDown, ChevronDown, ChevronRight, Calendar, DollarSign, AlertTriangle, X } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Badge from '../../../components/ui/Badge';
import { underwriterApi, paymentsApi } from '../../../api/endpoints';

interface LoanEntry {
  id: number;
  reference_number: string;
  applicant_id: number;
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

interface ScheduleEntry {
  id: number;
  installment_number: number;
  due_date: string;
  amount_due: number;
  amount_paid: number;
  status: string;
}

interface Transaction {
  id: number;
  amount: number;
  payment_type: string;
  payment_date: string;
  reference_number: string | null;
  status: string;
  notes: string | null;
  created_at: string;
}

const RISK_OPTIONS = ['all', 'A', 'B', 'C', 'D', 'E'];

type SortKey = keyof LoanEntry;

export default function LoanBook() {
  const [loans, setLoans] = useState<LoanEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [riskFilter, setRiskFilter] = useState('all');
  const [sortField, setSortField] = useState<SortKey>('created_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [schedule, setSchedule] = useState<ScheduleEntry[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const arrearsOnly = searchParams.get('arrears') === '1';

  const clearArrearsFilter = () => {
    searchParams.delete('arrears');
    setSearchParams(searchParams);
  };

  useEffect(() => {
    loadLoans();
  }, []);

  const loadLoans = async () => {
    try {
      const res = await underwriterApi.getLoanBook();
      setLoans(res.data);
    } catch { /* ignore */ }
    setLoading(false);
  };

  const toggleExpand = async (loanId: number) => {
    if (expandedId === loanId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(loanId);
    setDetailLoading(true);
    setSchedule([]);
    setTransactions([]);
    try {
      const [schedRes, histRes] = await Promise.all([
        paymentsApi.getSchedule(loanId),
        paymentsApi.getHistory(loanId),
      ]);
      setSchedule(schedRes.data || []);
      setTransactions(histRes.data || []);
    } catch { /* ignore */ }
    setDetailLoading(false);
  };

  const displayed = useMemo(() => {
    let result = [...loans];
    if (arrearsOnly) {
      result = result.filter(l => l.days_past_due > 0);
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
    result.sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return result;
  }, [loans, search, riskFilter, sortField, sortDir, arrearsOnly]);

  const handleSort = (field: SortKey) => {
    if (sortField === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  const SortIcon = ({ field }: { field: SortKey }) => {
    if (sortField !== field) return <ArrowUpDown size={12} className="opacity-30" />;
    return sortDir === 'asc'
      ? <ArrowUp size={12} className="text-[var(--color-primary)]" />
      : <ArrowDown size={12} className="text-[var(--color-primary)]" />;
  };

  const fmt = (val: number | null) =>
    val != null ? `TTD ${val.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '—';

  const riskColor = (band: string | null) => {
    const colors: Record<string, string> = { A: 'text-emerald-400', B: 'text-cyan-400', C: 'text-amber-400', D: 'text-orange-400', E: 'text-red-400' };
    return colors[band || ''] || 'text-gray-400';
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-[var(--color-text-muted)]">Loading loan book...</div>;
  }

  const columns: { key: SortKey; label: string }[] = [
    { key: 'reference_number', label: 'Reference' },
    { key: 'applicant_name', label: 'Applicant' },
    { key: 'amount_approved', label: 'Disbursed Amount' },
    { key: 'term_months', label: 'Term' },
    { key: 'interest_rate', label: 'Rate' },
    { key: 'monthly_payment', label: 'Monthly PMT' },
    { key: 'risk_band', label: 'Risk' },
    { key: 'credit_score', label: 'Score' },
    { key: 'outstanding_balance', label: 'Outstanding' },
    { key: 'days_past_due', label: 'DPD' },
    { key: 'disbursed_date', label: 'Disbursed' },
  ];

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
            <p className="text-sm text-[var(--color-text-muted)]">
              {displayed.length} disbursed loan{displayed.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
      </div>

      {/* Arrears filter banner */}
      {arrearsOnly && (
        <div className="flex items-center justify-between rounded-lg border-2 border-red-400/50 bg-red-50 dark:bg-red-950/30 px-4 py-2.5">
          <div className="flex items-center space-x-2">
            <AlertTriangle size={16} className="text-red-500" />
            <span className="text-sm font-semibold text-red-700 dark:text-red-400">
              Showing only loans in arrears ({displayed.length} loan{displayed.length !== 1 ? 's' : ''})
            </span>
          </div>
          <button
            onClick={clearArrearsFilter}
            className="flex items-center space-x-1 text-xs text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300 transition-colors"
          >
            <X size={14} />
            <span>Clear filter</span>
          </button>
        </div>
      )}

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
      </Card>

      {/* Table */}
      <Card padding="none">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                <th className="px-2 py-3 w-8"></th>
                {columns.map(col => (
                  <th
                    key={col.key}
                    className="px-4 py-3 text-left cursor-pointer hover:text-[var(--color-text)] whitespace-nowrap"
                    onClick={() => handleSort(col.key)}
                  >
                    <div className="flex items-center space-x-1">
                      <span>{col.label}</span>
                      <SortIcon field={col.key} />
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {displayed.map(loan => (
                <Fragment key={loan.id}>
                  <tr
                    className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] cursor-pointer transition-colors"
                  >
                    <td className="px-2 py-3 text-center">
                      <button
                        onClick={(e) => { e.stopPropagation(); toggleExpand(loan.id); }}
                        className="p-1 rounded hover:bg-[var(--color-bg)] text-[var(--color-text-muted)]"
                      >
                        {expandedId === loan.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      </button>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-[var(--color-primary)] cursor-pointer" onClick={() => navigate(`/backoffice/review/${loan.id}`)}>{loan.reference_number}</td>
                    <td className="px-4 py-3">
                      <Link to={`/backoffice/customers/${loan.applicant_id}`} className="hover:text-[var(--color-primary)] transition-colors">
                        {loan.applicant_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">{fmt(loan.amount_approved)}</td>
                    <td className="px-4 py-3">{loan.term_months}mo</td>
                    <td className="px-4 py-3">{loan.interest_rate ? `${loan.interest_rate}%` : '—'}</td>
                    <td className="px-4 py-3 whitespace-nowrap">{fmt(loan.monthly_payment)}</td>
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
                    <td className="px-4 py-3 text-[var(--color-text-muted)] whitespace-nowrap">
                      {loan.disbursed_date || '—'}
                    </td>
                  </tr>
                  {expandedId === loan.id && (
                    <tr key={`${loan.id}-detail`} className="bg-[var(--color-bg)]/50">
                      <td colSpan={columns.length + 1} className="px-4 py-4">
                        {detailLoading ? (
                          <p className="text-sm text-[var(--color-text-muted)] text-center py-4">Loading...</p>
                        ) : (
                          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            {/* Payment Calendar */}
                            <div>
                              <h4 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-3 flex items-center gap-2">
                                <Calendar size={14} /> Payment Calendar
                              </h4>
                              {schedule.length > 0 ? (
                                <div className="border border-[var(--color-border)] rounded-lg overflow-auto max-h-64">
                                  <table className="w-full text-xs">
                                    <thead>
                                      <tr className="bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]">
                                        <th className="px-3 py-2 text-left">#</th>
                                        <th className="px-3 py-2 text-left">Due Date</th>
                                        <th className="px-3 py-2 text-right">Amount Due</th>
                                        <th className="px-3 py-2 text-right">Paid</th>
                                        <th className="px-3 py-2 text-left">Status</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {schedule.map(s => (
                                        <tr key={s.id} className="border-t border-[var(--color-border)]/50">
                                          <td className="px-3 py-1.5">{s.installment_number}</td>
                                          <td className="px-3 py-1.5">{new Date(s.due_date).toLocaleDateString()}</td>
                                          <td className="px-3 py-1.5 text-right">{fmt(s.amount_due)}</td>
                                          <td className="px-3 py-1.5 text-right">{fmt(s.amount_paid)}</td>
                                          <td className="px-3 py-1.5">
                                            <Badge variant={s.status === 'paid' ? 'success' : s.status === 'overdue' ? 'danger' : 'warning'}>
                                              {s.status}
                                            </Badge>
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              ) : (
                                <p className="text-sm text-[var(--color-text-muted)]">No payment schedule</p>
                              )}
                            </div>

                            {/* Transactions */}
                            <div>
                              <h4 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-3 flex items-center gap-2">
                                <DollarSign size={14} /> Transactions
                              </h4>
                              {transactions.length > 0 ? (
                                <div className="border border-[var(--color-border)] rounded-lg overflow-auto max-h-64">
                                  <table className="w-full text-xs">
                                    <thead>
                                      <tr className="bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]">
                                        <th className="px-3 py-2 text-left">Date</th>
                                        <th className="px-3 py-2 text-right">Amount</th>
                                        <th className="px-3 py-2 text-left">Type</th>
                                        <th className="px-3 py-2 text-left">Ref</th>
                                        <th className="px-3 py-2 text-left">Status</th>
                                        <th className="px-3 py-2 text-left">Notes</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {transactions.map(t => (
                                        <tr key={t.id} className="border-t border-[var(--color-border)]/50">
                                          <td className="px-3 py-1.5">{new Date(t.payment_date).toLocaleDateString()}</td>
                                          <td className="px-3 py-1.5 text-right font-medium">{fmt(t.amount)}</td>
                                          <td className="px-3 py-1.5 capitalize">{t.payment_type.replace(/_/g, ' ')}</td>
                                          <td className="px-3 py-1.5 font-mono text-[var(--color-text-muted)]">{t.reference_number || '—'}</td>
                                          <td className="px-3 py-1.5">
                                            <Badge variant={t.status === 'completed' ? 'success' : t.status === 'failed' ? 'danger' : 'warning'}>
                                              {t.status}
                                            </Badge>
                                          </td>
                                          <td className="px-3 py-1.5 text-[var(--color-text-muted)] max-w-[120px] truncate">{t.notes || '—'}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              ) : (
                                <p className="text-sm text-[var(--color-text-muted)]">No transactions recorded</p>
                              )}
                            </div>
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {displayed.length === 0 && (
                <tr>
                  <td colSpan={columns.length + 1} className="px-4 py-8 text-center text-[var(--color-text-muted)]">
                    No disbursed loans found
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
