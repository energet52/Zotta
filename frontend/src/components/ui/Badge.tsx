import { clsx } from 'clsx';

interface BadgeProps {
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
  children: React.ReactNode;
  className?: string;
}

export default function Badge({ variant = 'default', children, className }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        {
          'bg-gray-100 text-gray-800': variant === 'default',
          'bg-green-100 text-green-800': variant === 'success',
          'bg-yellow-100 text-yellow-800': variant === 'warning',
          'bg-red-100 text-red-800': variant === 'danger',
          'bg-blue-100 text-blue-800': variant === 'info',
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
    disbursed: { variant: 'success', label: 'Disbursed' },
    cancelled: { variant: 'default', label: 'Cancelled' },
  };

  const config = map[status] || { variant: 'default' as const, label: status };
  return <Badge variant={config.variant}>{config.label}</Badge>;
}
