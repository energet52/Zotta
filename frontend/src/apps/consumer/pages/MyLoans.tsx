import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Wallet, Calendar, ChevronRight, CreditCard, AlertTriangle,
  DollarSign, FileText, X,
} from 'lucide-react';
import { clsx } from 'clsx';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
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

const DISPUTE_CATEGORIES = [
  { value: 'incorrect_amount', label: 'Incorrect Amount' },
  { value: 'payment_not_reflected', label: 'Payment Not Reflected' },
  { value: 'unauthorized_charges', label: 'Unauthorized Charges' },
  { value: 'duplicate_charges', label: 'Duplicate Charges' },
  { value: 'service_issue', label: 'Service Issue' },
  { value: 'other', label: 'Other' },
];

export default function MyLoans() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [schedules, setSchedules] = useState<Record<number, ScheduleItem[]>>({});
  const [loadingSchedule, setLoadingSchedule] = useState<Record<number, boolean>>({});
  // Dispute form
  const [showDispute, setShowDispute] = useState<number | null>(null);
  const [disputeForm, setDisputeForm] = useState({ category: 'incorrect_amount', description: '' });
  const [disputeSubmitted, setDisputeSubmitted] = useState(false);
  // Payment plan request
  const [showPaymentPlan, setShowPaymentPlan] = useState<number | null>(null);
  const [planSubmitted, setPlanSubmitted] = useState(false);

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
    return sched.find((s) => s.status !== 'paid' && Number(s.amount_paid || 0) < Number(s.amount_due || 0)) || null;
  };

  const getPaidCount = (sched: ScheduleItem[] | undefined) => {
    if (!sched?.length) return 0;
    return sched.filter((s) => s.status === 'paid').length;
  };

  const getOverdueInfo = (sched: ScheduleItem[] | undefined) => {
    if (!sched?.length) return null;
    const today = new Date();
    const overdueItems = sched.filter(s => {
      const due = new Date(s.due_date);
      return due < today && s.status !== 'paid' && Number(s.amount_paid || 0) < Number(s.amount_due || 0);
    });
    if (overdueItems.length === 0) return null;
    const totalOverdue = overdueItems.reduce((sum, s) => sum + (Number(s.amount_due) - Number(s.amount_paid || 0)), 0);
    const oldest = overdueItems.reduce((min, s) => new Date(s.due_date) < new Date(min.due_date) ? s : min);
    const dpd = Math.floor((today.getTime() - new Date(oldest.due_date).getTime()) / (1000 * 60 * 60 * 24));
    const principalOverdue = overdueItems.reduce((sum, s) => sum + Number(s.principal), 0);
    const interestOverdue = overdueItems.reduce((sum, s) => sum + Number(s.interest), 0);
    const feeOverdue = overdueItems.reduce((sum, s) => sum + Number(s.fee || 0), 0);
    return { totalOverdue, dpd, count: overdueItems.length, principalOverdue, interestOverdue, feeOverdue };
  };

  const handleSubmitDispute = () => {
    // In a real app this would call an API
    setDisputeSubmitted(true);
    setTimeout(() => {
      setShowDispute(null);
      setDisputeSubmitted(false);
      setDisputeForm({ category: 'incorrect_amount', description: '' });
    }, 2000);
  };

  const handleRequestPaymentPlan = () => {
    setPlanSubmitted(true);
    setTimeout(() => {
      setShowPaymentPlan(null);
      setPlanSubmitted(false);
    }, 2000);
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
            const overdueInfo = sched ? getOverdueInfo(sched) : null;

            return (
              <Card key={app.id} padding="none" className="overflow-hidden">
                {/* Overdue Banner */}
                {overdueInfo && (
                  <div className="bg-red-500/10 border-b border-red-500/20 px-4 py-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <AlertTriangle size={16} className="text-red-400" />
                        <span className="font-semibold text-red-400">
                          Overdue: {formatCurrency(overdueInfo.totalOverdue)}
                        </span>
                        <span className="text-xs text-[var(--color-text-muted)]">({overdueInfo.dpd} days past due)</span>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={(e) => { e.stopPropagation(); setShowPaymentPlan(showPaymentPlan === app.id ? null : app.id); setShowDispute(null); }}
                          className="px-3 py-1 text-xs rounded-lg bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 transition-colors"
                        >
                          <FileText size={12} className="inline mr-1" /> Request Plan
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); setShowDispute(showDispute === app.id ? null : app.id); setShowPaymentPlan(null); }}
                          className="px-3 py-1 text-xs rounded-lg bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 transition-colors"
                        >
                          <AlertTriangle size={12} className="inline mr-1" /> Raise Dispute
                        </button>
                      </div>
                    </div>
                    {/* Balance Breakdown */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-2 text-xs">
                      <div>
                        <span className="text-[var(--color-text-muted)]">Principal</span>
                        <p className="font-medium text-red-300">{formatCurrency(overdueInfo.principalOverdue)}</p>
                      </div>
                      <div>
                        <span className="text-[var(--color-text-muted)]">Interest</span>
                        <p className="font-medium text-red-300">{formatCurrency(overdueInfo.interestOverdue)}</p>
                      </div>
                      <div>
                        <span className="text-[var(--color-text-muted)]">Fees</span>
                        <p className="font-medium text-red-300">{formatCurrency(overdueInfo.feeOverdue)}</p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Payment Plan Request Form */}
                {showPaymentPlan === app.id && (
                  <div className="bg-blue-500/5 border-b border-blue-500/20 px-4 py-4">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="font-semibold text-blue-400 flex items-center gap-2">
                        <FileText size={16} /> Request Payment Plan
                      </h3>
                      <button onClick={() => setShowPaymentPlan(null)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                        <X size={16} />
                      </button>
                    </div>
                    {planSubmitted ? (
                      <div className="text-center py-4">
                        <DollarSign size={24} className="mx-auto text-emerald-400 mb-2" />
                        <p className="text-emerald-400 font-semibold">Request Submitted</p>
                        <p className="text-sm text-[var(--color-text-muted)]">We'll contact you within 24 hours.</p>
                      </div>
                    ) : (
                      <div>
                        <p className="text-sm text-[var(--color-text-muted)] mb-3">
                          We can help restructure your overdue payments into manageable installments.
                          A collections agent will contact you to discuss your options.
                        </p>
                        <Button onClick={handleRequestPaymentPlan}>
                          <DollarSign size={14} className="mr-1" /> Submit Request
                        </Button>
                      </div>
                    )}
                  </div>
                )}

                {/* Dispute Form */}
                {showDispute === app.id && (
                  <div className="bg-purple-500/5 border-b border-purple-500/20 px-4 py-4">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="font-semibold text-purple-400 flex items-center gap-2">
                        <AlertTriangle size={16} /> Raise a Dispute
                      </h3>
                      <button onClick={() => setShowDispute(null)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                        <X size={16} />
                      </button>
                    </div>
                    {disputeSubmitted ? (
                      <div className="text-center py-4">
                        <FileText size={24} className="mx-auto text-emerald-400 mb-2" />
                        <p className="text-emerald-400 font-semibold">Dispute Submitted</p>
                        <p className="text-sm text-[var(--color-text-muted)]">Reference: DSP-{Date.now().toString(36).toUpperCase()}</p>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        <div>
                          <label className="block text-sm text-[var(--color-text-muted)] mb-1">Category</label>
                          <select
                            value={disputeForm.category}
                            onChange={e => setDisputeForm(f => ({ ...f, category: e.target.value }))}
                            className="w-full h-[38px] px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
                          >
                            {DISPUTE_CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                          </select>
                        </div>
                        <div>
                          <label className="block text-sm text-[var(--color-text-muted)] mb-1">Description</label>
                          <textarea
                            value={disputeForm.description}
                            onChange={e => setDisputeForm(f => ({ ...f, description: e.target.value }))}
                            rows={3}
                            placeholder="Describe your dispute in detail..."
                            className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
                          />
                        </div>
                        <Button onClick={handleSubmitDispute} disabled={!disputeForm.description.trim()}>
                          Submit Dispute
                        </Button>
                      </div>
                    )}
                  </div>
                )}

                <button
                  onClick={() => toggleExpand(app.id)}
                  className="w-full flex items-center justify-between p-4 text-left hover:bg-[var(--color-surface-hover)] transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${overdueInfo ? 'bg-red-500/20' : 'bg-[var(--color-primary)]/20'}`}>
                      {overdueInfo ? <AlertTriangle size={20} className="text-red-400" /> : <Wallet size={20} className="text-[var(--color-primary)]" />}
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
                        <div className="grid grid-cols-1 sm:grid-cols-2 sm:grid-cols-4 gap-4">
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
                              {nextPayment ? new Date(nextPayment.due_date).toLocaleDateString() : '—'}
                            </p>
                          </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex flex-wrap gap-2">
                          <Link
                            to={`/applications/${app.id}`}
                            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white text-sm font-medium hover:opacity-90 transition-opacity"
                          >
                            <DollarSign size={14} />
                            Make Payment
                          </Link>
                          {overdueInfo && (
                            <>
                              <button
                                onClick={() => { setShowPaymentPlan(app.id); setShowDispute(null); }}
                                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-500/20 text-blue-400 text-sm font-medium hover:bg-blue-500/30 transition-colors"
                              >
                                <FileText size={14} /> Request Payment Plan
                              </button>
                              <button
                                onClick={() => { setShowDispute(app.id); setShowPaymentPlan(null); }}
                                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-500/20 text-purple-400 text-sm font-medium hover:bg-purple-500/30 transition-colors"
                              >
                                <AlertTriangle size={14} /> Raise Dispute
                              </button>
                            </>
                          )}
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
