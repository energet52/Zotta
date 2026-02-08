import { useState } from 'react';
import { Download, FileText } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { reportsApi } from '../../../api/endpoints';

export default function Reports() {
  const [exporting, setExporting] = useState('');

  const handleExportLoanBook = async () => {
    setExporting('loan_book');
    try {
      const response = await reportsApi.exportLoanBook();
      const blob = new Blob([response.data], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `loan_book_${new Date().toISOString().split('T')[0]}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      alert('Export failed');
    } finally {
      setExporting('');
    }
  };

  const reports = [
    {
      id: 'loan_book',
      title: 'Loan Book Report',
      description: 'Complete list of all loan applications with status, amounts, rates, and dates.',
      format: 'CSV',
      action: handleExportLoanBook,
    },
    {
      id: 'decision_audit',
      title: 'Decision Audit Report',
      description: 'Audit trail of all decisions made, including engine outcomes and underwriter overrides.',
      format: 'CSV',
      action: () => alert('Coming soon'),
    },
    {
      id: 'underwriter_performance',
      title: 'Underwriter Performance Report',
      description: 'Applications processed per underwriter, average processing time, override rate.',
      format: 'CSV',
      action: () => alert('Coming soon'),
    },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Reports</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {reports.map((report) => (
          <Card key={report.id}>
            <div className="flex items-start space-x-3 mb-4">
              <div className="p-2 bg-blue-50 rounded-lg">
                <FileText className="text-blue-600" size={20} />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold">{report.title}</h3>
                <p className="text-sm text-gray-500 mt-1">{report.description}</p>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-400">Format: {report.format}</span>
              <Button
                size="sm"
                variant="outline"
                onClick={report.action}
                isLoading={exporting === report.id}
              >
                <Download size={14} className="mr-1" />
                Export
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
