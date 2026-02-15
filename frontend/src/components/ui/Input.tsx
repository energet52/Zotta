import type { InputHTMLAttributes } from 'react';
import { forwardRef } from 'react';
import { clsx } from 'clsx';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, className, id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');

    return (
      <div className="w-full">
        {label && (
          <label htmlFor={inputId} className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={clsx(
            'w-full h-[38px] px-3 py-2 border rounded-lg text-sm transition-colors bg-[var(--color-surface)] text-[var(--color-text)]',
            'focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:border-transparent',
            'placeholder:text-[var(--color-text-muted)]',
            error ? 'border-red-500 focus:ring-red-400' : 'border-[var(--color-border)]',
            className
          )}
          {...props}
        />
        {error && <p className="mt-1 text-xs text-[var(--color-danger)]">{error}</p>}
        {helperText && !error && <p className="mt-1 text-xs text-[var(--color-text-muted)]">{helperText}</p>}
      </div>
    );
  }
);

Input.displayName = 'Input';
export default Input;
