import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
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
  { value: '', label: 'All Active' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'under_review', label: 'Under Review' },
  { value: 'credit_check', label: 'Credit Check' },
  { value: 'decision_pending', label: 'Decision Pending' },
  { value: 'awaiting_documents', label: 'Awaiting Documents' },
];

export default function Queue() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');

  const loadQueue = () => {
    setLoading(true);
    underwriterApi.getQueue(filter || undefined)
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
        <h1 className="text-2xl font-bold">Application Queue</h1>
        <div className="flex items-center space-x-2">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-[var(--color-primary)]"
          >
            {STATUS_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
          <Button variant="secondary" size="sm" onClick={loadQueue}>Refresh</Button>
        </div>
      </div>

      <Card>
        {loading ? (
          <p className="text-center py-8 text-gray-400">Loading queue...</p>
        ) : applications.length === 0 ? (
          <p className="text-center py-8 text-gray-400">No applications in queue</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-3 px-3 text-gray-500 font-medium">Reference</th>
                  <th className="text-left py-3 px-3 text-gray-500 font-medium">Amount</th>
                  <th className="text-left py-3 px-3 text-gray-500 font-medium">Term</th>
                  <th className="text-left py-3 px-3 text-gray-500 font-medium">Purpose</th>
                  <th className="text-left py-3 px-3 text-gray-500 font-medium">Status</th>
                  <th className="text-left py-3 px-3 text-gray-500 font-medium">Submitted</th>
                  <th className="text-left py-3 px-3 text-gray-500 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {applications.map((app) => (
                  <tr key={app.id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-3 px-3 font-medium">
                      <Link to={`/backoffice/review/${app.id}`} className="text-[var(--color-primary)] hover:underline">
                        {app.reference_number}
                      </Link>
                    </td>
                    <td className="py-3 px-3">TTD {app.amount_requested.toLocaleString()}</td>
                    <td className="py-3 px-3">{app.term_months}m</td>
                    <td className="py-3 px-3 capitalize">{app.purpose.replace('_', ' ')}</td>
                    <td className="py-3 px-3">{getStatusBadge(app.status)}</td>
                    <td className="py-3 px-3 text-gray-500">
                      {app.submitted_at ? new Date(app.submitted_at).toLocaleDateString() : '-'}
                    </td>
                    <td className="py-3 px-3">
                      <div className="flex items-center space-x-2">
                        <Link to={`/backoffice/review/${app.id}`}>
                          <Button size="sm" variant="outline">Review</Button>
                        </Link>
                        {!app.assigned_underwriter_id && (
                          <Button size="sm" variant="ghost" onClick={() => handleAssign(app.id)}>
                            Assign to Me
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
