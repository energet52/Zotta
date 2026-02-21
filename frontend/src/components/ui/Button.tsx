import type { ButtonHTMLAttributes } from 'react';
import { forwardRef } from 'react';
import { clsx } from 'clsx';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'outline' | 'success' | 'warning';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', isLoading, className, children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={clsx(
          'inline-flex items-center justify-center font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed',
          {
            'bg-[var(--color-primary)] text-white hover:brightness-110 focus:ring-[var(--color-primary)]': variant === 'primary',
            'bg-[var(--color-surface-hover,#f1f5f9)] text-[var(--color-text-muted)] hover:brightness-110 focus:ring-gray-300 border border-[var(--color-border)]': variant === 'secondary',
            'bg-[var(--color-danger)] text-white hover:brightness-110 focus:ring-red-400': variant === 'danger',
            'text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover,#f1f5f9)] focus:ring-gray-300': variant === 'ghost',
            'border-2 border-[var(--color-primary)] text-[var(--color-primary)] hover:bg-[var(--color-primary)]/10 focus:ring-[var(--color-primary)]': variant === 'outline',
            'bg-[var(--color-success)] text-white hover:brightness-110 focus:ring-green-400': variant === 'success',
            'bg-[var(--color-warning)] text-black hover:brightness-110 focus:ring-yellow-400': variant === 'warning',
            'px-3 py-1.5 text-sm': size === 'sm',
            'px-4 py-2 text-sm': size === 'md',
            'px-4 sm:px-6 py-3 text-base': size === 'lg',
          },
          className
        )}
        {...props}
      >
        {isLoading && (
          <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
export default Button;
