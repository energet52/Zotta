import type { ReactNode } from 'react';
import { clsx } from 'clsx';

interface ResponsiveTableProps {
  children: ReactNode;
  className?: string;
  tableClassName?: string;
}

export default function ResponsiveTable({
  children,
  className,
  tableClassName,
}: ResponsiveTableProps) {
  return (
    <div className={clsx('overflow-x-auto max-w-full', className)}>
      <table className={clsx('w-full text-sm', tableClassName)}>{children}</table>
    </div>
  );
}
