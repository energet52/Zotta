import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FileText, CheckCircle, XCircle, Clock, TrendingUp, DollarSign, Users, BarChart3 } from 'lucide-react';
import Card from '../../../components/ui/Card';
import { reportsApi } from '../../../api/endpoints';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

interface DashboardData {
  total_applications: number;
  pending_review: number;
  approved: number;
  declined: number;
  total_disbursed: number;
  approval_rate: number;
  avg_processing_days: number;
  avg_loan_amount: number;
  applications_by_status: Record<string, number>;
  risk_distribution: Record<string, number>;
  monthly_volume: { year: number; month: number; count: number; volume: number }[];
}

const RISK_COLORS: Record<string, string> = {
  A: '#38a169', B: '#68d391', C: '#ecc94b', D: '#ed8936', E: '#e53e3e',
};

export default function UnderwriterDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    reportsApi.getDashboard()
      .then((res) => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-12 text-gray-400">Loading dashboard...</div>;
  if (!data) return <div className="text-center py-12 text-red-500">Failed to load dashboard</div>;

  const riskData = Object.entries(data.risk_distribution).map(([band, count]) => ({
    name: `Band ${band}`, value: count, fill: RISK_COLORS[band] || '#a0aec0',
  }));

  const monthlyData = data.monthly_volume.map((m) => ({
    name: `${m.year}-${String(m.month).padStart(2, '0')}`,
    count: m.count,
    volume: m.volume,
  }));

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <Link to="/backoffice/queue" className="text-sm text-[var(--color-primary)] hover:underline">
          View Queue &rarr;
        </Link>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Card padding="sm">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-blue-50 rounded-lg"><FileText className="text-blue-600" size={20} /></div>
            <div>
              <p className="text-2xl font-bold">{data.total_applications}</p>
              <p className="text-xs text-gray-500">Total Applications</p>
            </div>
          </div>
        </Card>
        <Card padding="sm">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-yellow-50 rounded-lg"><Clock className="text-yellow-600" size={20} /></div>
            <div>
              <p className="text-2xl font-bold">{data.pending_review}</p>
              <p className="text-xs text-gray-500">Pending Review</p>
            </div>
          </div>
        </Card>
        <Card padding="sm">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-green-50 rounded-lg"><TrendingUp className="text-green-600" size={20} /></div>
            <div>
              <p className="text-2xl font-bold">{data.approval_rate}%</p>
              <p className="text-xs text-gray-500">Approval Rate</p>
            </div>
          </div>
        </Card>
        <Card padding="sm">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-purple-50 rounded-lg"><DollarSign className="text-purple-600" size={20} /></div>
            <div>
              <p className="text-2xl font-bold">TTD {(data.avg_loan_amount / 1000).toFixed(0)}k</p>
              <p className="text-xs text-gray-500">Avg Loan Amount</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <h3 className="font-semibold mb-4">Monthly Volume</h3>
          {monthlyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={monthlyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-center text-gray-400 py-12">No data available</p>
          )}
        </Card>

        <Card>
          <h3 className="font-semibold mb-4">Risk Distribution</h3>
          {riskData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={riskData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                  {riskData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-center text-gray-400 py-12">No data available</p>
          )}
        </Card>
      </div>
    </div>
  );
}
