import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Wallet, Calendar, ChevronRight, CreditCard } from 'lucide-react';
import { clsx } from 'clsx';
import Card from '../../../components/ui/Card';
import { loanApi, paymentsApi } from '../../../api/endpoints';

interface Application {
  id: number;
  reference_number: string;
  amount_requested: number;
  amount_approved: number | null;
  term_months: number;
  purpose: string;
  status: string;
  monthly_payment: number | null;
  created_at: string;
}

interface ScheduleItem {
  id: number;
  installment_number: number;
  due_date: string;
  principal: number;
  interest: number;
  fee: number;
  amount_due: number;
  amount_paid: number;
  status: string;
}

function formatCurrency(n: number) {
  return `TTD ${n.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
}

export default function MyLoans() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [schedules, setSchedules] = useState<Record<number, ScheduleItem[]>>({});
  const [loadingSchedule, setLoadingSchedule] = useState<Record<number, boolean>>({});

  const disbursed = applications.filter((a) => a.status === 'disbursed');

  useEffect(() => {
    loanApi
      .list()
      .then((res) => setApplications(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const loadSchedule = (appId: number) => {
    if (schedules[appId]) return;
    setLoadingSchedule((prev) => ({ ...prev, [appId]: true }));
    paymentsApi
      .getSchedule(appId)
      .then((res) => setSchedules((prev) => ({ ...prev, [appId]: res.data })))
      .catch(() => {})
      .finally(() => setLoadingSchedule((prev) => ({ ...prev, [appId]: false })));
  };

  const toggleExpand = (appId: number) => {
    if (expandedId === appId) {
      setExpandedId(null);
    } else {
      setExpandedId(appId);
      loadSchedule(appId);
    }
  };

  const getOutstanding = (app: Application, sched: ScheduleItem[] | undefined) => {
    const total = Number(app.amount_approved || app.amount_requested);
    if (!sched?.length) return total;
    const paid = sched.reduce((sum, s) => sum + Number(s.amount_paid || 0), 0);
    return Math.max(0, total - paid);
  };

  const getProgress = (app: Application, sched: ScheduleItem[] | undefined) => {
    const total = Number(app.amount_approved || app.amount_requested);
    if (!sched?.length || total <= 0) return 0;
    const paid = sched.reduce((sum, s) => sum + Number(s.amount_paid || 0), 0);
    return Math.min(100, (paid / total) * 100);
  };

  const getNextPayment = (sched: ScheduleItem[] | undefined) => {
    if (!sched?.length) return null;
    const unpaid = sched.find((s) => s.status !== 'paid' && Number(s.amount_paid || 0) < Number(s.amount_due || 0));
    return unpaid || null;
  };

  const getPaidCount = (sched: ScheduleItem[] | undefined) => {
    if (!sched?.length) return 0;
    return sched.filter((s) => s.status === 'paid').length;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-[var(--color-text-muted)]">Loading...</div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-[var(--color-text)] flex items-center gap-2">
          <Wallet size={28} />
          My Loans
        </h1>
        <p className="text-[var(--color-text-muted)] mt-1">
          Track your disbursed loans, repayment progress, and payment calendar
        </p>
      </div>

      {disbursed.length === 0 ? (
        <Card className="py-16 text-center">
          <CreditCard size={48} className="mx-auto text-[var(--color-text-muted)] mb-4" />
          <p className="text-[var(--color-text-muted)] mb-2">No active loans yet</p>
          <p className="text-sm text-[var(--color-text-muted)] mb-6">
            Your disbursed loans will appear here once approved and funded.
          </p>
          <Link
            to="/apply"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white text-sm font-medium hover:opacity-90 transition-opacity"
          >
            Apply for a loan
            <ChevronRight size={16} />
          </Link>
        </Card>
      ) : (
        <div className="space-y-4">
          {disbursed.map((app) => {
            const sched = schedules[app.id];
            const isLoading = loadingSchedule[app.id];
            const outstanding = getOutstanding(app, sched);
            const progress = getProgress(app, sched);
            const nextPayment = getNextPayment(sched);
            const paidCount = getPaidCount(sched);
            const totalInstallments = sched?.length ?? app.term_months;
            const isExpanded = expandedId === app.id;

            return (
              <Card key={app.id} padding="none" className="overflow-hidden">
                <button
                  onClick={() => toggleExpand(app.id)}
                  className="w-full flex items-center justify-between p-4 text-left hover:bg-[var(--color-surface-hover)] transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-lg bg-[var(--color-primary)]/20 flex items-center justify-center">
                      <Wallet size={20} className="text-[var(--color-primary)]" />
                    </div>
                    <div>
                      <p className="font-semibold text-[var(--color-text)]">{app.reference_number}</p>
                      <p className="text-sm text-[var(--color-text-muted)]">
                        {formatCurrency(Number(app.amount_approved || app.amount_requested))} &middot; {app.term_months} months
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                    <div className="text-right hidden sm:block">
                      <p className="text-xs text-[var(--color-text-muted)]">Outstanding</p>
                      <p className="font-semibold text-[var(--color-text)]">{formatCurrency(outstanding)}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-20 h-1.5 rounded-full bg-[var(--color-border)] overflow-hidden">
                        <div
                          className="h-full rounded-full bg-[var(--color-success)] transition-all"
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                      <span className="text-xs text-[var(--color-text-muted)]">{Math.round(progress)}%</span>
                    </div>
                    <ChevronRight size={20} className={clsx('text-[var(--color-text-muted)] transition-transform', isExpanded && 'rotate-90')} />
                  </div>
                </button>

                {isExpanded && (
                  <div className="border-t border-[var(--color-border)] p-4 space-y-4">
                    {isLoading ? (
                      <p className="text-sm text-[var(--color-text-muted)] py-4 text-center">Loading schedule...</p>
                    ) : (
                      <>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                          <div className="p-3 rounded-lg bg-[var(--color-bg)]">
                            <p className="text-xs text-[var(--color-text-muted)]">Outstanding</p>
                            <p className="font-semibold text-[var(--color-text)]">{formatCurrency(outstanding)}</p>
                          </div>
                          <div className="p-3 rounded-lg bg-[var(--color-bg)]">
                            <p className="text-xs text-[var(--color-text-muted)]">Monthly Payment</p>
                            <p className="font-semibold text-[var(--color-primary)]">
                              {app.monthly_payment ? formatCurrency(Number(app.monthly_payment)) : '—'}
                            </p>
                          </div>
                          <div className="p-3 rounded-lg bg-[var(--color-bg)]">
                            <p className="text-xs text-[var(--color-text-muted)]">Payments Made</p>
                            <p className="font-semibold text-[var(--color-text)]">
                              {paidCount} / {totalInstallments}
                            </p>
                          </div>
                          <div className="p-3 rounded-lg bg-[var(--color-bg)]">
                            <p className="text-xs text-[var(--color-text-muted)]">Next Due</p>
                            <p className="font-semibold text-[var(--color-text)]">
                              {nextPayment
                                ? new Date(nextPayment.due_date).toLocaleDateString()
                                : '—'}
                            </p>
                          </div>
                        </div>

                        <div>
                          <h3 className="text-sm font-semibold text-[var(--color-text-muted)] mb-3 flex items-center gap-2">
                            <Calendar size={14} />
                            Payment Calendar
                          </h3>
                          <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="bg-[var(--color-surface-hover)]">
                                  <th className="text-left py-2.5 px-3 text-[var(--color-text-muted)] font-medium">#</th>
                                  <th className="text-left py-2.5 px-3 text-[var(--color-text-muted)] font-medium">Due Date</th>
                                  <th className="text-right py-2.5 px-3 text-[var(--color-text-muted)] font-medium">Amount</th>
                                  <th className="text-right py-2.5 px-3 text-[var(--color-text-muted)] font-medium">Paid</th>
                                  <th className="text-left py-2.5 px-3 text-[var(--color-text-muted)] font-medium">Status</th>
                                </tr>
                              </thead>
                              <tbody>
                                {(sched || []).map((row) => (
                                  <tr key={row.id} className="border-t border-[var(--color-border)]">
                                    <td className="py-2 px-3 text-[var(--color-text)]">{row.installment_number}</td>
                                    <td className="py-2 px-3 text-[var(--color-text)]">
                                      {new Date(row.due_date).toLocaleDateString()}
                                    </td>
                                    <td className="py-2 px-3 text-right text-[var(--color-text)]">
                                      {formatCurrency(Number(row.amount_due))}
                                    </td>
                                    <td className="py-2 px-3 text-right text-[var(--color-success)]">
                                      {formatCurrency(Number(row.amount_paid || 0))}
                                    </td>
                                    <td className="py-2 px-3">
                                      <span
                                        className={clsx(
                                          'text-xs font-medium px-2 py-0.5 rounded',
                                          row.status === 'paid' && 'bg-emerald-500/20 text-emerald-400',
                                          row.status === 'overdue' && 'bg-red-500/20 text-red-400',
                                          row.status === 'partial' && 'bg-amber-500/20 text-amber-400',
                                          ['upcoming', 'due'].includes(row.status) && 'bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]'
                                        )}
                                      >
                                        {row.status}
                                      </span>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>

                        <Link
                          to={`/applications/${app.id}`}
                          className="inline-flex items-center gap-2 text-sm font-medium text-[var(--color-primary)] hover:underline"
                        >
                          View full details & make payment
                          <ChevronRight size={14} />
                        </Link>
                      </>
                    )}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
