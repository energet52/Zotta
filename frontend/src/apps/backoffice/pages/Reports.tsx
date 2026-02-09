import { useEffect, useState } from 'react';
import {
  Download, FileText, BarChart3, Users, Clock, Shield,
  TrendingUp, DollarSign, AlertTriangle, Banknote, Calendar, RefreshCw
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { reportsApi } from '../../../api/endpoints';

interface ReportHistoryItem {
  id: number;
  report_type: string;
  report_name: string;
  file_format: string;
  created_at: string;
}

const REPORT_DEFINITIONS = [
  { type: 'aged', title: 'Aged Report', description: 'Outstanding loans grouped by days past due (Current, 30, 60, 90, 120+)', icon: Clock, color: 'var(--color-danger)' },
  { type: 'exposure', title: 'Exposure Report', description: 'Total exposure by risk band, status, and loan purpose', icon: Shield, color: 'var(--color-warning)' },
  { type: 'interest_fees', title: 'Interest & Fees', description: 'Projected and earned interest, fees summary', icon: DollarSign, color: 'var(--color-success)' },
  { type: 'loan_statement', title: 'Loan Statement', description: 'Individual loan statement with payment schedule and history', icon: FileText, color: 'var(--color-primary)' },
  { type: 'portfolio_summary', title: 'Portfolio Summary', description: 'Overview of entire loan portfolio health and metrics', icon: TrendingUp, color: 'var(--color-cyan, #22d3ee)' },
  { type: 'loan_book', title: 'Loan Book', description: 'Complete loan book with all applications and details', icon: FileText, color: 'var(--color-primary)' },
  { type: 'decision_audit', title: 'Decision Audit', description: 'Engine decisions and underwriter overrides audit trail', icon: BarChart3, color: 'var(--color-warning)' },
  { type: 'underwriter_performance', title: 'Underwriter Performance', description: 'Processed counts, avg time, approvals per underwriter', icon: Users, color: 'var(--color-success)' },
  { type: 'collection_report', title: 'Collection Report', description: 'Collection activity summary by outcome and channel', icon: AlertTriangle, color: 'var(--color-danger)' },
  { type: 'disbursement', title: 'Disbursement Report', description: 'Loans disbursed in selected period with amounts and rates', icon: Banknote, color: 'var(--color-success)' },
];

export default function Reports() {
  const [generating, setGenerating] = useState('');
  const [history, setHistory] = useState<ReportHistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 90);
    return d.toISOString().split('T')[0];
  });
  const [dateTo, setDateTo] = useState(() => new Date().toISOString().split('T')[0]);
  const [appIdInput, setAppIdInput] = useState('');

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      const res = await reportsApi.getHistory();
      setHistory(res.data);
    } catch { /* ignore */ }
    setLoadingHistory(false);
  };

  const handleGenerate = async (reportType: string) => {
    setGenerating(reportType);
    try {
      const params: any = { date_from: dateFrom, date_to: dateTo };
      if (reportType === 'loan_statement' && appIdInput) {
        params.application_id = parseInt(appIdInput);
      }
      const res = await reportsApi.generateReport(reportType, params);
      // Decode and download
      const csvContent = atob(res.data.file_data);
      const blob = new Blob([csvContent], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${reportType}_${new Date().toISOString().split('T')[0]}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
      // Refresh history
      loadHistory();
    } catch {
      alert('Report generation failed');
    }
    setGenerating('');
  };

  const handleDownloadHistorical = async (id: number, reportType: string) => {
    try {
      const res = await reportsApi.downloadHistorical(id);
      const blob = new Blob([res.data], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${reportType}_${id}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      alert('Download failed');
    }
  };

  const inputClass = "px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--color-text)]">Reports</h1>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">Generate, download, and manage operational reports</p>
      </div>

      {/* Date Range */}
      <Card>
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-xs text-[var(--color-text-muted)] mb-1">Date From</label>
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className="block text-xs text-[var(--color-text-muted)] mb-1">Date To</label>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className="block text-xs text-[var(--color-text-muted)] mb-1">App ID (for Loan Statement)</label>
            <input type="number" value={appIdInput} onChange={e => setAppIdInput(e.target.value)} className={inputClass} placeholder="e.g. 42" />
          </div>
        </div>
      </Card>

      {/* Report Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {REPORT_DEFINITIONS.map(report => (
          <Card key={report.type}>
            <div className="flex items-start space-x-3 mb-4">
              <div className="p-2 rounded-lg" style={{ backgroundColor: `color-mix(in srgb, ${report.color} 15%, transparent)` }}>
                <report.icon size={20} style={{ color: report.color }} />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-[var(--color-text)] text-sm">{report.title}</h3>
                <p className="text-xs text-[var(--color-text-muted)] mt-1">{report.description}</p>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-[var(--color-text-muted)]">CSV</span>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleGenerate(report.type)}
                isLoading={generating === report.type}
              >
                <Download size={14} className="mr-1" />
                Generate
              </Button>
            </div>
          </Card>
        ))}
      </div>

      {/* Report History */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-[var(--color-text)]">Report History</h3>
          <Button size="sm" variant="secondary" onClick={loadHistory}>
            <RefreshCw size={14} className="mr-1" /> Refresh
          </Button>
        </div>
        {loadingHistory ? (
          <p className="text-[var(--color-text-muted)] text-center py-4">Loading...</p>
        ) : history.length === 0 ? (
          <p className="text-[var(--color-text-muted)] text-center py-4">No reports generated yet</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                  <th className="px-4 py-2 text-left">Report</th>
                  <th className="px-4 py-2 text-left">Type</th>
                  <th className="px-4 py-2 text-left">Format</th>
                  <th className="px-4 py-2 text-left">Generated</th>
                  <th className="px-4 py-2 text-left">Action</th>
                </tr>
              </thead>
              <tbody>
                {history.map(item => (
                  <tr key={item.id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]">
                    <td className="px-4 py-2 text-[var(--color-text)]">{item.report_name}</td>
                    <td className="px-4 py-2 capitalize text-[var(--color-text-muted)]">{item.report_type.replace(/_/g, ' ')}</td>
                    <td className="px-4 py-2 uppercase text-xs text-[var(--color-text-muted)]">{item.file_format}</td>
                    <td className="px-4 py-2 text-xs text-[var(--color-text-muted)]">
                      {new Date(item.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2">
                      <button
                        onClick={() => handleDownloadHistorical(item.id, item.report_type)}
                        className="text-[var(--color-primary)] hover:text-[var(--color-primary-light)] text-xs"
                      >
                        <Download size={14} />
                      </button>
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
