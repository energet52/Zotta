import { clsx } from 'clsx';

interface BadgeProps {
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'purple' | 'cyan';
  children: React.ReactNode;
  className?: string;
}

export default function Badge({ variant = 'default', children, className }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        {
          'bg-gray-100 text-gray-800 dark-badge-default': variant === 'default',
          'bg-emerald-500/15 text-emerald-400 dark-badge-success': variant === 'success',
          'bg-amber-500/15 text-amber-400 dark-badge-warning': variant === 'warning',
          'bg-red-500/15 text-red-400 dark-badge-danger': variant === 'danger',
          'bg-sky-500/15 text-sky-400 dark-badge-info': variant === 'info',
          'bg-purple-500/15 text-purple-400': variant === 'purple',
          'bg-cyan-500/15 text-cyan-400': variant === 'cyan',
        },
        className
      )}
    >
      {children}
    </span>
  );
}

// Helper to map loan status to badge variant
export function getStatusBadge(status: string) {
  const map: Record<string, { variant: BadgeProps['variant']; label: string }> = {
    draft: { variant: 'default', label: 'Draft' },
    submitted: { variant: 'info', label: 'Submitted' },
    under_review: { variant: 'info', label: 'Under Review' },
    awaiting_documents: { variant: 'warning', label: 'Awaiting Documents' },
    credit_check: { variant: 'info', label: 'Credit Check' },
    decision_pending: { variant: 'warning', label: 'Decision Pending' },
    approved: { variant: 'success', label: 'Approved' },
    declined: { variant: 'danger', label: 'Declined' },
    offer_sent: { variant: 'success', label: 'Offer Sent' },
    accepted: { variant: 'success', label: 'Accepted' },
    rejected_by_applicant: { variant: 'danger', label: 'Rejected' },
    disbursed: { variant: 'cyan', label: 'Disbursed' },
    cancelled: { variant: 'default', label: 'Cancelled' },
    voided: { variant: 'danger', label: 'Voided' },
    counter_proposed: { variant: 'purple', label: 'Counter Proposed' },
    uploaded: { variant: 'info', label: 'Uploaded' },
    verified: { variant: 'success', label: 'Verified' },
    rejected: { variant: 'danger', label: 'Rejected' },
  };

  const config = map[status] || { variant: 'default' as const, label: status };
  return <Badge variant={config.variant}>{config.label}</Badge>;
}
