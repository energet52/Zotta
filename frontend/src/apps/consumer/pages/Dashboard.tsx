import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FileText, Plus, Clock, CheckCircle, XCircle } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { getStatusBadge } from '../../../components/ui/Badge';
import { loanApi } from '../../../api/endpoints';
import { useAuthStore } from '../../../store/authStore';

interface Application {
  id: number;
  reference_number: string;
  amount_requested: number;
  term_months: number;
  purpose: string;
  status: string;
  created_at: string;
  amount_approved: number | null;
  interest_rate: number | null;
  monthly_payment: number | null;
}

export default function Dashboard() {
  const { user } = useAuthStore();
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loanApi.list().then((res) => {
      setApplications(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const activeApps = applications.filter((a) => !['declined', 'cancelled', 'rejected_by_applicant'].includes(a.status));
  const approvedApps = applications.filter((a) => ['approved', 'offer_sent', 'accepted', 'disbursed'].includes(a.status));

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Welcome back, {user?.first_name}!
          </h1>
          <p className="text-gray-500 mt-1">Manage your loan applications</p>
        </div>
        <Link to="/apply">
          <Button>
            <Plus size={16} className="mr-2" />
            New Application
          </Button>
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <Card>
          <div className="flex items-center space-x-3">
            <div className="p-3 bg-blue-50 rounded-lg">
              <FileText className="text-blue-600" size={24} />
            </div>
            <div>
              <p className="text-2xl font-bold">{applications.length}</p>
              <p className="text-sm text-gray-500">Total Applications</p>
            </div>
          </div>
        </Card>
        <Card>
          <div className="flex items-center space-x-3">
            <div className="p-3 bg-yellow-50 rounded-lg">
              <Clock className="text-yellow-600" size={24} />
            </div>
            <div>
              <p className="text-2xl font-bold">{activeApps.length}</p>
              <p className="text-sm text-gray-500">Active</p>
            </div>
          </div>
        </Card>
        <Card>
          <div className="flex items-center space-x-3">
            <div className="p-3 bg-green-50 rounded-lg">
              <CheckCircle className="text-green-600" size={24} />
            </div>
            <div>
              <p className="text-2xl font-bold">{approvedApps.length}</p>
              <p className="text-sm text-gray-500">Approved</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Recent Applications */}
      <Card>
        <h2 className="text-lg font-semibold mb-4">Recent Applications</h2>
        {loading ? (
          <p className="text-gray-400 text-center py-8">Loading...</p>
        ) : applications.length === 0 ? (
          <div className="text-center py-12">
            <FileText className="mx-auto text-gray-300 mb-3" size={48} />
            <p className="text-gray-500 mb-4">No applications yet</p>
            <Link to="/apply">
              <Button>Start Your Application</Button>
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-3 px-2 text-gray-500 font-medium">Reference</th>
                  <th className="text-left py-3 px-2 text-gray-500 font-medium">Amount</th>
                  <th className="text-left py-3 px-2 text-gray-500 font-medium">Term</th>
                  <th className="text-left py-3 px-2 text-gray-500 font-medium">Purpose</th>
                  <th className="text-left py-3 px-2 text-gray-500 font-medium">Status</th>
                  <th className="text-left py-3 px-2 text-gray-500 font-medium">Date</th>
                </tr>
              </thead>
              <tbody>
                {applications.map((app) => (
                  <tr key={app.id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-3 px-2">
                      <Link to={`/applications/${app.id}`} className="text-[var(--color-primary)] font-medium hover:underline">
                        {app.reference_number}
                      </Link>
                    </td>
                    <td className="py-3 px-2">TTD {app.amount_requested.toLocaleString()}</td>
                    <td className="py-3 px-2">{app.term_months} months</td>
                    <td className="py-3 px-2 capitalize">{app.purpose.replace('_', ' ')}</td>
                    <td className="py-3 px-2">{getStatusBadge(app.status)}</td>
                    <td className="py-3 px-2 text-gray-500">{new Date(app.created_at).toLocaleDateString()}</td>
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
