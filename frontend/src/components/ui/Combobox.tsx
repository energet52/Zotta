/**
 * Accessible searchable combobox — best-practice pattern for dropdowns with search.
 * Uses aria attributes, keyboard navigation, and click-outside to close.
 */
import { useState, useRef, useEffect, useMemo } from 'react';
import { ChevronDown, Check } from 'lucide-react';
import { clsx } from 'clsx';

export interface ComboboxOption {
  id: number;
  name: string;
}

interface ComboboxProps<T extends { id: number } = ComboboxOption> {
  value: number | null;
  options: T[];
  onChange: (id: number, label: string) => void;
  placeholder?: string;
  label?: string;
  disabled?: boolean;
  className?: string;
  /** Render label for option (default: o.name). Use for branches etc. */
  formatOption?: (opt: T) => string;
}

export default function Combobox<T extends { id: number } = ComboboxOption>({
  value,
  options,
  onChange,
  placeholder = 'Select...',
  label,
  disabled,
  className,
  formatOption,
}: ComboboxProps<T>) {
  const getLabel = formatOption ?? ((o: T) => ('name' in o ? String((o as { name?: string }).name) : String(o.id)));
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlightIndex, setHighlightIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selected = options.find((o) => o.id === value);
  const displayValue = selected ? getLabel(selected) : '';

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => getLabel(o).toLowerCase().includes(q));
  }, [query, options, getLabel]);

  const selectOption = (opt: T) => {
    onChange(opt.id, getLabel(opt));
    setQuery('');
    setOpen(false);
    setHighlightIndex(0);
  };

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    setHighlightIndex(0);
  }, [query, filtered]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault();
        setOpen(true);
      }
      return;
    }
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightIndex((i) => Math.min(i + 1, filtered.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightIndex((i) => Math.max(i - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (filtered[highlightIndex]) selectOption(filtered[highlightIndex]);
        break;
      case 'Escape':
        e.preventDefault();
        setOpen(false);
        setQuery('');
        break;
      default:
        break;
    }
  };

  return (
    <div ref={containerRef} className={clsx('relative', className)}>
      {label && (
        <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1.5">
          {label}
        </label>
      )}
      <div
        className={clsx(
          'flex items-center gap-2 w-full h-[38px] px-3 rounded-lg border text-sm transition-colors',
          'bg-[var(--color-surface)] border-[var(--color-border)] text-[var(--color-text)]',
          'focus-within:ring-2 focus-within:ring-[var(--color-primary)]/50 focus-within:border-[var(--color-primary)]',
          open && 'ring-2 ring-[var(--color-primary)]/50 border-[var(--color-primary)]',
          disabled && 'opacity-50 cursor-not-allowed'
        )}
      >
        <input
          ref={inputRef}
          type="text"
          value={open ? query : displayValue}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          autoComplete="off"
          role="combobox"
          aria-expanded={open}
          aria-autocomplete="list"
          aria-controls="combobox-listbox"
          aria-activedescendant={filtered[highlightIndex] ? `option-${filtered[highlightIndex].id}` : undefined}
          className="flex-1 min-w-0 bg-transparent outline-none placeholder:text-[var(--color-text-muted)]"
        />
        <button
          type="button"
          onClick={() => setOpen(!open)}
          disabled={disabled}
          className="shrink-0 p-0.5 text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
          aria-label={open ? 'Close' : 'Open'}
        >
          <ChevronDown
            size={16}
            className={clsx('transition-transform', open && 'rotate-180')}
          />
        </button>
      </div>

      {open && (
        <ul
          id="combobox-listbox"
          role="listbox"
          className="absolute z-50 mt-1 w-full max-h-56 overflow-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xl py-1"
        >
          {filtered.length === 0 ? (
            <li className="px-3 py-2 text-sm text-[var(--color-text-muted)]">No matches</li>
          ) : (
            filtered.map((opt, i) => (
              <li
                key={opt.id}
                id={`option-${opt.id}`}
                role="option"
                aria-selected={opt.id === value}
                className={clsx(
                  'flex items-center justify-between px-3 py-2.5 cursor-pointer text-sm transition-colors',
                  i === highlightIndex && 'bg-[var(--color-surface-hover)]',
                  opt.id === value && 'text-[var(--color-primary)]'
                )}
                onMouseEnter={() => setHighlightIndex(i)}
                onClick={() => selectOption(opt)}
              >
                <span>{getLabel(opt)}</span>
                {opt.id === value && <Check size={14} className="shrink-0" />}
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
