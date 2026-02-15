import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { AlertTriangle } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Badge from '../../../components/ui/Badge';
import { collectionsApi } from '../../../api/endpoints';

interface CollectionEntry {
  id: number;
  reference_number: string;
  applicant_id: number;
  applicant_name: string;
  amount_approved: number | null;
  amount_due: number;
  days_past_due: number;
  last_contact: string | null;
  next_action: string | null;
  total_paid: number;
  outstanding_balance: number;
  phone: string | null;
}

export default function Collections() {
  const [queue, setQueue] = useState<CollectionEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    loadQueue();
  }, []);

  const loadQueue = async () => {
    try {
      const res = await collectionsApi.getQueue();
      setQueue(res.data);
    } catch { /* ignore */ }
    setLoading(false);
  };

  const fmt = (val: number | null) =>
    val != null ? `TTD ${val.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '—';

  const severityBadge = (dpd: number) => {
    if (dpd >= 90) return { variant: 'danger' as const, label: '90+ Days' };
    if (dpd >= 60) return { variant: 'warning' as const, label: '60+ Days' };
    if (dpd >= 30) return { variant: 'warning' as const, label: '30+ Days' };
    return { variant: 'info' as const, label: `${dpd} Days` };
  };

  // Summary stats
  const totalOverdue = queue.reduce((sum, q) => sum + q.amount_due, 0);
  const severe = queue.filter(q => q.days_past_due >= 90).length;
  const moderate = queue.filter(q => q.days_past_due >= 30 && q.days_past_due < 90).length;
  const mild = queue.filter(q => q.days_past_due < 30).length;

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-[var(--color-text-muted)]">Loading collections...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-3">
        <div className="p-2 bg-[var(--color-danger)]/15 rounded-lg">
          <AlertTriangle className="text-[var(--color-danger)]" size={24} />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Collections</h1>
          <p className="text-sm text-[var(--color-text-muted)]">{queue.length} overdue accounts</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <div className="text-sm text-[var(--color-text-muted)]">Total Overdue</div>
          <div className="text-2xl font-bold text-[var(--color-danger)] mt-1">{fmt(totalOverdue)}</div>
        </Card>
        <Card>
          <div className="text-sm text-[var(--color-text-muted)]">Severe (90+ days)</div>
          <div className="text-2xl font-bold text-red-400 mt-1">{severe}</div>
        </Card>
        <Card>
          <div className="text-sm text-[var(--color-text-muted)]">Moderate (30-90)</div>
          <div className="text-2xl font-bold text-amber-400 mt-1">{moderate}</div>
        </Card>
        <Card>
          <div className="text-sm text-[var(--color-text-muted)]">Mild (&lt;30)</div>
          <div className="text-2xl font-bold text-yellow-400 mt-1">{mild}</div>
        </Card>
      </div>

      {/* Queue Table */}
      <Card padding="none">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                <th className="px-4 py-3 text-left">Reference</th>
                <th className="px-4 py-3 text-left">Applicant</th>
                <th className="px-4 py-3 text-left">Loan Amount</th>
                <th className="px-4 py-3 text-left">Amount Due</th>
                <th className="px-4 py-3 text-left">DPD</th>
                <th className="px-4 py-3 text-left">Outstanding</th>
                <th className="px-4 py-3 text-left">Last Contact</th>
                <th className="px-4 py-3 text-left">Next Action</th>
                <th className="px-4 py-3 text-left">Phone</th>
              </tr>
            </thead>
            <tbody>
              {queue.map(item => {
                const badge = severityBadge(item.days_past_due);
                return (
                  <tr
                    key={item.id}
                    className={`border-b border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] cursor-pointer transition-colors`}
                    onClick={() => navigate(`/backoffice/collections/${item.id}`)}
                  >
                    <td className="px-4 py-3 font-mono text-xs text-[var(--color-primary)]">{item.reference_number}</td>
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      <Link to={`/backoffice/customers/${item.applicant_id}`} className="hover:text-[var(--color-primary)] transition-colors">
                        {item.applicant_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">{fmt(item.amount_approved)}</td>
                    <td className="px-4 py-3 whitespace-nowrap font-bold text-[var(--color-danger)]">{fmt(item.amount_due)}</td>
                    <td className="px-4 py-3"><Badge variant={badge.variant}>{badge.label}</Badge></td>
                    <td className="px-4 py-3 whitespace-nowrap">{fmt(item.outstanding_balance)}</td>
                    <td className="px-4 py-3 text-xs">
                      {item.last_contact ? new Date(item.last_contact).toLocaleDateString() : 'Never'}
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {item.next_action || '—'}
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--color-text-muted)]">{item.phone || '—'}</td>
                  </tr>
                );
              })}
              {queue.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-[var(--color-text-muted)]">
                    No overdue accounts found
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
