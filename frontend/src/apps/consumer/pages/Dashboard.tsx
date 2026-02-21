import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  FileText, Plus, Clock, CheckCircle, AlertTriangle,
  CalendarClock, DollarSign, MessageSquare, MessageCircle,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { getStatusBadge } from '../../../components/ui/Badge';
import { loanApi, paymentsApi } from '../../../api/endpoints';
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

interface NextPayment {
  due_date: string;
  amount_due: number;
  installment_number: number;
}

interface LoanSummary {
  application_id: number;
  reference_number: string;
  loan_amount: number;
  monthly_payment: number;
  interest_rate: number;
  term_months: number;
  remaining_balance: number;
  total_paid: number;
  total_installments: number;
  paid_installments: number;
  next_payment: NextPayment | null;
  overdue_amount: number;
  days_past_due: number;
  in_arrears: boolean;
}

const fmt = (n: number) => `TTD ${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function daysUntil(dateStr: string): number {
  const d = new Date(dateStr);
  const now = new Date();
  return Math.ceil((d.getTime() - now.getTime()) / 86400000);
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function Dashboard() {
  const { user } = useAuthStore();
  const [applications, setApplications] = useState<Application[]>([]);
  const [loanSummaries, setLoanSummaries] = useState<LoanSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      loanApi.list(),
      paymentsApi.getMyLoansSummary(),
    ]).then(([appsRes, summaryRes]) => {
      setApplications(appsRes.data);
      setLoanSummaries(summaryRes.data.loans || []);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const activeApps = applications.filter((a) => !['declined', 'cancelled', 'rejected_by_applicant'].includes(a.status));
  const approvedApps = applications.filter((a) => ['approved', 'offer_sent', 'accepted', 'disbursed'].includes(a.status));

  // Aggregate arrears across all loans
  const totalOverdue = loanSummaries.reduce((sum, l) => sum + l.overdue_amount, 0);
  const anyArrears = totalOverdue > 0;

  // Soonest next payment across all loans
  const upcomingPayments = loanSummaries
    .filter((l) => l.next_payment)
    .sort((a, b) => (a.next_payment!.due_date).localeCompare(b.next_payment!.due_date));

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">
            Welcome back, {user?.first_name}!
          </h1>
          <p className="text-[var(--color-text-muted)] mt-1">Manage your loan applications</p>
        </div>
        <div className="flex gap-2">
          <Link
            to="/chat"
            className="inline-flex items-center px-4 py-2 border-2 border-[var(--color-primary)] text-[var(--color-primary)] rounded-lg hover:bg-[var(--color-primary)]/10 transition-colors font-medium text-sm"
          >
            <MessageCircle size={16} className="mr-2" />
            Chat with Zotta
          </Link>
          <Link to="/apply">
            <Button>
              <Plus size={16} className="mr-2" />
              New Application
            </Button>
          </Link>
        </div>
      </div>

      {/* ── Arrears Alert Banner ── */}
      {anyArrears && (
        <div className="mb-6 rounded-xl border-2 border-red-400/50 bg-red-50 dark:bg-red-950/30 p-4 flex items-start space-x-3">
          <AlertTriangle className="text-red-500 shrink-0 mt-0.5" size={22} />
          <div className="flex-1">
            <h3 className="font-semibold text-red-700 dark:text-red-400">Payment Overdue</h3>
            <p className="text-sm text-red-600 dark:text-red-300 mt-0.5">
              You have {fmt(totalOverdue)} overdue across your loans. Please make a payment as soon as possible to avoid additional charges.
            </p>
          </div>
          <Link to="/notifications">
            <Button size="sm" variant="primary" className="bg-red-600 hover:bg-red-700 border-red-600 shrink-0">
              <MessageSquare size={14} className="mr-1.5" />
              Contact Lender
            </Button>
          </Link>
        </div>
      )}

      {/* ── Active Loan Summary Cards ── */}
      {loanSummaries.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-[var(--color-text)] mb-4">Your Active Loans</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {loanSummaries.map((loan) => {
              const daysLeft = loan.next_payment ? daysUntil(loan.next_payment.due_date) : null;
              const isOverdue = daysLeft !== null && daysLeft < 0;
              const isDueSoon = daysLeft !== null && daysLeft >= 0 && daysLeft <= 7;
              const progressPct = loan.total_installments > 0
                ? Math.round((loan.paid_installments / loan.total_installments) * 100)
                : 0;

              return (
                <Card key={loan.application_id} className="relative overflow-hidden">
                  {/* Arrears stripe */}
                  {loan.in_arrears && (
                    <div className="absolute top-0 left-0 right-0 h-1 bg-red-500" />
                  )}

                  {/* Header */}
                  <div className="flex items-center justify-between mb-4">
                    <Link
                      to={`/applications/${loan.application_id}`}
                      className="text-[var(--color-primary)] font-semibold hover:underline"
                    >
                      Loan {loan.reference_number}
                    </Link>
                    <span className="text-xs text-[var(--color-text-muted)]">
                      {loan.interest_rate}% &middot; {loan.term_months} months
                    </span>
                  </div>

                  {/* Key Metrics */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
                    {/* Next Payment */}
                    <div className={`rounded-lg p-3 ${
                      isOverdue
                        ? 'bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800'
                        : isDueSoon
                          ? 'bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800'
                          : 'bg-[var(--color-bg)] border border-[var(--color-border)]'
                    }`}>
                      <div className="flex items-center space-x-1.5 mb-1">
                        <CalendarClock size={14} className={
                          isOverdue ? 'text-red-500' : isDueSoon ? 'text-amber-500' : 'text-[var(--color-text-muted)]'
                        } />
                        <span className="text-[10px] uppercase font-semibold tracking-wider text-[var(--color-text-muted)]">
                          Next Payment
                        </span>
                      </div>
                      {loan.next_payment ? (
                        <>
                          <p className={`text-lg font-bold ${
                            isOverdue ? 'text-red-600 dark:text-red-400' : 'text-[var(--color-text)]'
                          }`}>
                            {fmt(loan.next_payment.amount_due)}
                          </p>
                          <p className={`text-xs mt-0.5 ${
                            isOverdue
                              ? 'text-red-500 font-semibold'
                              : isDueSoon
                                ? 'text-amber-600 dark:text-amber-400 font-medium'
                                : 'text-[var(--color-text-muted)]'
                          }`}>
                            {isOverdue
                              ? `Overdue by ${Math.abs(daysLeft!)} day${Math.abs(daysLeft!) !== 1 ? 's' : ''}`
                              : daysLeft === 0
                                ? 'Due today'
                                : daysLeft === 1
                                  ? 'Due tomorrow'
                                  : `Due ${formatDate(loan.next_payment.due_date)}`}
                          </p>
                        </>
                      ) : (
                        <p className="text-sm text-green-600 dark:text-green-400 font-medium">Fully paid!</p>
                      )}
                    </div>

                    {/* Remaining Balance */}
                    <div className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg p-3">
                      <div className="flex items-center space-x-1.5 mb-1">
                        <DollarSign size={14} className="text-[var(--color-text-muted)]" />
                        <span className="text-[10px] uppercase font-semibold tracking-wider text-[var(--color-text-muted)]">
                          Remaining
                        </span>
                      </div>
                      <p className="text-lg font-bold text-[var(--color-text)]">
                        {fmt(loan.remaining_balance)}
                      </p>
                      <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
                        of {fmt(loan.loan_amount + (loan.remaining_balance + loan.total_paid - loan.loan_amount))} total
                      </p>
                    </div>
                  </div>

                  {/* Arrears section */}
                  {loan.in_arrears && (
                    <div className="rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 p-3 mb-4 flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <AlertTriangle size={16} className="text-red-500" />
                        <div>
                          <p className="text-sm font-semibold text-red-700 dark:text-red-400">
                            {fmt(loan.overdue_amount)} overdue
                          </p>
                          <p className="text-xs text-red-500">
                            {loan.days_past_due} day{loan.days_past_due !== 1 ? 's' : ''} past due
                          </p>
                        </div>
                      </div>
                      <Link to={`/applications/${loan.application_id}`}>
                        <Button size="sm" variant="primary" className="bg-red-600 hover:bg-red-700 border-red-600">
                          <MessageSquare size={12} className="mr-1" />
                          Contact
                        </Button>
                      </Link>
                    </div>
                  )}

                  {/* Progress Bar */}
                  <div>
                    <div className="flex items-center justify-between text-xs text-[var(--color-text-muted)] mb-1.5">
                      <span>{loan.paid_installments} of {loan.total_installments} payments</span>
                      <span>{progressPct}%</span>
                    </div>
                    <div className="h-2 rounded-full bg-[var(--color-border)] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-[var(--color-primary)] transition-all duration-500"
                        style={{ width: `${progressPct}%` }}
                      />
                    </div>
                  </div>

                  {/* Monthly payment footer */}
                  <div className="mt-3 pt-3 border-t border-[var(--color-border)] flex items-center justify-between text-xs text-[var(--color-text-muted)]">
                    <span>Monthly payment: <span className="font-semibold text-[var(--color-text)]">{fmt(loan.monthly_payment)}</span></span>
                    <span>Paid so far: <span className="font-semibold text-[var(--color-text)]">{fmt(loan.total_paid)}</span></span>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Stats ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <Card>
          <div className="flex items-center space-x-3">
            <div className="p-3 bg-[var(--color-primary)]/20 rounded-lg">
              <FileText className="text-[var(--color-primary)]" size={24} />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--color-text)]">{applications.length}</p>
              <p className="text-sm text-[var(--color-text-muted)]">Total Applications</p>
            </div>
          </div>
        </Card>
        <Card>
          <div className="flex items-center space-x-3">
            <div className="p-3 bg-[var(--color-warning)]/20 rounded-lg">
              <Clock className="text-[var(--color-warning)]" size={24} />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--color-text)]">{activeApps.length}</p>
              <p className="text-sm text-[var(--color-text-muted)]">Active</p>
            </div>
          </div>
        </Card>
        <Card>
          <div className="flex items-center space-x-3">
            <div className="p-3 bg-[var(--color-success)]/20 rounded-lg">
              <CheckCircle className="text-[var(--color-success)]" size={24} />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--color-text)]">{approvedApps.length}</p>
              <p className="text-sm text-[var(--color-text-muted)]">Approved</p>
            </div>
          </div>
        </Card>
      </div>

      {/* ── Upcoming Payments Quick View ── */}
      {upcomingPayments.length > 0 && (
        <Card className="mb-8">
          <h2 className="text-lg font-semibold mb-3 text-[var(--color-text)] flex items-center space-x-2">
            <CalendarClock size={18} className="text-[var(--color-primary)]" />
            <span>Upcoming Payments</span>
          </h2>
          <div className="divide-y divide-[var(--color-border)]">
            {upcomingPayments.map((loan) => {
              const np = loan.next_payment!;
              const dl = daysUntil(np.due_date);
              const isOverdue = dl < 0;
              const isDueSoon = dl >= 0 && dl <= 7;
              return (
                <div key={loan.application_id} className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
                  <div className="flex items-center space-x-3">
                    <div className={`w-2 h-2 rounded-full ${
                      isOverdue ? 'bg-red-500' : isDueSoon ? 'bg-amber-500' : 'bg-green-500'
                    }`} />
                    <div>
                      <Link
                        to={`/applications/${loan.application_id}`}
                        className="text-sm font-medium text-[var(--color-text)] hover:text-[var(--color-primary)]"
                      >
                        {loan.reference_number}
                      </Link>
                      <p className={`text-xs ${
                        isOverdue ? 'text-red-500 font-semibold' : isDueSoon ? 'text-amber-600 dark:text-amber-400' : 'text-[var(--color-text-muted)]'
                      }`}>
                        {isOverdue
                          ? `${Math.abs(dl)} day${Math.abs(dl) !== 1 ? 's' : ''} overdue`
                          : dl === 0
                            ? 'Due today'
                            : dl === 1
                              ? 'Due tomorrow'
                              : `Due in ${dl} days — ${formatDate(np.due_date)}`}
                      </p>
                    </div>
                  </div>
                  <span className={`font-semibold text-sm ${isOverdue ? 'text-red-600 dark:text-red-400' : 'text-[var(--color-text)]'}`}>
                    {fmt(np.amount_due)}
                  </span>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* ── Recent Applications ── */}
      <Card>
        <h2 className="text-lg font-semibold mb-4 text-[var(--color-text)]">Recent Applications</h2>
        {loading ? (
          <p className="text-[var(--color-text-muted)] text-center py-8">Loading...</p>
        ) : applications.length === 0 ? (
          <div className="text-center py-12">
            <FileText className="mx-auto text-[var(--color-text-muted)] mb-3" size={48} />
            <p className="text-[var(--color-text-muted)] mb-4">No applications yet</p>
            <Link to="/apply">
              <Button>Start Your Application</Button>
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto max-w-full">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="text-left py-3 px-2 text-[var(--color-text-muted)] font-medium">Reference</th>
                  <th className="text-left py-3 px-2 text-[var(--color-text-muted)] font-medium">Amount</th>
                  <th className="text-left py-3 px-2 text-[var(--color-text-muted)] font-medium">Term</th>
                  <th className="text-left py-3 px-2 text-[var(--color-text-muted)] font-medium">Status</th>
                  <th className="text-left py-3 px-2 text-[var(--color-text-muted)] font-medium">Date</th>
                </tr>
              </thead>
              <tbody>
                {applications.map((app) => (
                  <tr key={app.id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]">
                    <td className="py-3 px-2">
                      <Link to={`/applications/${app.id}`} className="text-[var(--color-primary)] font-medium hover:underline">
                        {app.reference_number}
                      </Link>
                    </td>
                    <td className="py-3 px-2">TTD {app.amount_requested.toLocaleString()}</td>
                    <td className="py-3 px-2">{app.term_months} months</td>
                    <td className="py-3 px-2">{getStatusBadge(app.status)}</td>
                    <td className="py-3 px-2 text-[var(--color-text-muted)]">{new Date(app.created_at).toLocaleDateString()}</td>
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
