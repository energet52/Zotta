import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { getStatusBadge } from '../../../components/ui/Badge';
import { underwriterApi } from '../../../api/endpoints';

interface Application {
  id: number;
  reference_number: string;
  amount_requested: number;
  term_months: number;
  purpose: string;
  status: string;
  submitted_at: string | null;
  assigned_underwriter_id: number | null;
}

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

export default function Queue() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');

  const loadQueue = () => {
    setLoading(true);
    const params = filter === 'all' ? 'all' : filter || undefined;
    underwriterApi.getQueue(params)
      .then((res) => setApplications(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadQueue(); }, [filter]);

  const handleAssign = async (id: number) => {
    await underwriterApi.assign(id);
    loadQueue();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">Application Queue</h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">{applications.length} applications</p>
        </div>
        <div className="flex items-center space-x-3">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] focus:ring-2 focus:ring-[var(--color-primary)] focus:outline-none"
          >
            {STATUS_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
          <Button variant="secondary" size="sm" onClick={loadQueue}>
            <RefreshCw size={14} className="mr-1" /> Refresh
          </Button>
        </div>
      </div>

      <Card padding="none">
        {loading ? (
          <p className="text-center py-8 text-[var(--color-text-muted)]">Loading queue...</p>
        ) : applications.length === 0 ? (
          <p className="text-center py-8 text-[var(--color-text-muted)]">No applications found</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="text-left py-3 px-4 text-[var(--color-text-muted)] font-medium text-xs uppercase tracking-wider">Reference</th>
                  <th className="text-left py-3 px-4 text-[var(--color-text-muted)] font-medium text-xs uppercase tracking-wider">Amount</th>
                  <th className="text-left py-3 px-4 text-[var(--color-text-muted)] font-medium text-xs uppercase tracking-wider">Term</th>
                  <th className="text-left py-3 px-4 text-[var(--color-text-muted)] font-medium text-xs uppercase tracking-wider">Purpose</th>
                  <th className="text-left py-3 px-4 text-[var(--color-text-muted)] font-medium text-xs uppercase tracking-wider">Status</th>
                  <th className="text-left py-3 px-4 text-[var(--color-text-muted)] font-medium text-xs uppercase tracking-wider">Submitted</th>
                  <th className="text-left py-3 px-4 text-[var(--color-text-muted)] font-medium text-xs uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody>
                {applications.map((app) => (
                  <tr key={app.id} className="border-b border-[var(--color-border)]/50 hover:bg-[var(--color-surface-hover)] transition-colors">
                    <td className="py-3 px-4 font-medium">
                      <Link to={`/backoffice/review/${app.id}`} className="text-[var(--color-primary)] hover:text-[var(--color-primary-light)] transition-colors">
                        {app.reference_number}
                      </Link>
                    </td>
                    <td className="py-3 px-4 text-[var(--color-text)] font-medium">TTD {app.amount_requested.toLocaleString()}</td>
                    <td className="py-3 px-4 text-[var(--color-text-muted)]">{app.term_months}m</td>
                    <td className="py-3 px-4 text-[var(--color-text-muted)] capitalize">{app.purpose.replace(/_/g, ' ')}</td>
                    <td className="py-3 px-4">{getStatusBadge(app.status)}</td>
                    <td className="py-3 px-4 text-[var(--color-text-muted)]">
                      {app.submitted_at ? new Date(app.submitted_at).toLocaleDateString() : '-'}
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
