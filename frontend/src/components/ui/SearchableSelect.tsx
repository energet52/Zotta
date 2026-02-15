/**
 * SearchableSelect — a string-value combobox with type-ahead search.
 *
 * Matches Input component height exactly (h-[38px] = px-3 py-2 + border).
 * Implements WAI-ARIA combobox pattern with keyboard navigation.
 */
import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { ChevronDown, Check, X, Search } from 'lucide-react';
import { clsx } from 'clsx';

export interface SelectOption {
  value: string;
  label: string;
}

interface SearchableSelectProps {
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
  /** Override the label's Tailwind classes (default: text-sm) */
  labelClassName?: string;
  name?: string;
  disabled?: boolean;
  error?: string;
  className?: string;
  /** If true, shows a clear button when a value is selected */
  clearable?: boolean;
  /**
   * When true, if "Other" is selected the component shows a text input
   * for the user to type a custom value. The custom value becomes the
   * onChange output. The `otherLabel` defaults to "Other".
   */
  allowOther?: boolean;
  /** Label for the "Other" option (default: "Other") */
  otherLabel?: string;
  /** Placeholder for the custom text input shown when "Other" is selected */
  otherPlaceholder?: string;
}

export default function SearchableSelect({
  value,
  options,
  onChange,
  placeholder = 'Select...',
  label,
  labelClassName,
  name,
  disabled,
  error,
  className,
  clearable = true,
  allowOther = false,
  otherLabel = 'Other',
  otherPlaceholder = 'Please specify...',
}: SearchableSelectProps) {
  const OTHER_VALUE = '__other__';
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlightIndex, setHighlightIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const otherInputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // When allowOther is enabled, track if the user picked "Other"
  const [customText, setCustomText] = useState('');
  const [otherExplicit, setOtherExplicit] = useState(false);
  const isOtherSelected = allowOther && (otherExplicit || (value !== '' && !options.some((o) => o.value === value)));

  // Sync customText when the value is a custom "other" value (e.g. loaded from DB)
  useEffect(() => {
    if (isOtherSelected && customText !== value) {
      setCustomText(value);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  // Build effective options: append "Other" if allowOther
  const effectiveOptions = useMemo(() => {
    if (!allowOther) return options;
    return [...options, { value: OTHER_VALUE, label: otherLabel }];
  }, [options, allowOther, otherLabel, OTHER_VALUE]);

  const selected = effectiveOptions.find((o) =>
    isOtherSelected ? o.value === OTHER_VALUE : o.value === value
  );
  const displayValue = isOtherSelected ? `${otherLabel}: ${value}` : (selected?.label ?? '');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return effectiveOptions;
    return effectiveOptions.filter(
      (o) =>
        o.label.toLowerCase().includes(q) ||
        o.value.toLowerCase().includes(q)
    );
  }, [query, effectiveOptions]);

  const selectOption = useCallback(
    (opt: SelectOption) => {
      if (opt.value === OTHER_VALUE) {
        // When "Other" is picked, show the custom text input.
        setOtherExplicit(true);
        setCustomText('');
        onChange('');
        setTimeout(() => otherInputRef.current?.focus(), 0);
      } else {
        setOtherExplicit(false);
        onChange(opt.value);
      }
      setQuery('');
      setOpen(false);
      setHighlightIndex(0);
    },
    [onChange, OTHER_VALUE]
  );

  const handleClear = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onChange('');
      setQuery('');
      setCustomText('');
      setOtherExplicit(false);
      inputRef.current?.focus();
    },
    [onChange]
  );

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery('');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Reset highlight when query or filtered list changes
  useEffect(() => {
    setHighlightIndex(0);
  }, [query, filtered.length]);

  // Scroll highlighted item into view
  useEffect(() => {
    if (open && listRef.current) {
      const item = listRef.current.children[highlightIndex] as HTMLElement | undefined;
      item?.scrollIntoView({ block: 'nearest' });
    }
  }, [highlightIndex, open]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open) {
      if (e.key === 'Enter' || e.key === 'ArrowDown' || e.key === 'ArrowUp') {
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
      case 'Tab':
        setOpen(false);
        setQuery('');
        break;
      default:
        break;
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
    if (!open) setOpen(true);
  };

  const handleTriggerClick = () => {
    if (disabled) return;
    setOpen(!open);
    if (!open) {
      // Focus and select text on open
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  };

  return (
    <div ref={containerRef} className={clsx('relative w-full', className)}>
      {label && (
        <label className={labelClassName || 'block text-sm font-medium text-[var(--color-text-muted)] mb-1'}>
          {label}
        </label>
      )}

      {/* Hidden input for form compatibility */}
      {name && <input type="hidden" name={name} value={value} />}

      {/* Trigger */}
      <div
        onClick={handleTriggerClick}
        className={clsx(
          'flex items-center w-full h-[38px] px-3 rounded-lg border text-sm transition-colors cursor-pointer',
          'bg-[var(--color-surface)] text-[var(--color-text)]',
          open
            ? 'ring-2 ring-[var(--color-primary)]/50 border-[var(--color-primary)]'
            : error
              ? 'border-red-500'
              : 'border-[var(--color-border)]',
          'focus-within:ring-2 focus-within:ring-[var(--color-primary)]/50 focus-within:border-[var(--color-primary)]',
          disabled && 'opacity-50 cursor-not-allowed'
        )}
      >
        {open ? (
          <>
            <Search size={14} className="shrink-0 mr-2 text-[var(--color-text-muted)]" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder={displayValue || placeholder}
              disabled={disabled}
              autoComplete="off"
              role="combobox"
              aria-expanded={open}
              aria-autocomplete="list"
              aria-controls="ss-listbox"
              aria-activedescendant={
                filtered[highlightIndex]
                  ? `ss-option-${filtered[highlightIndex].value}`
                  : undefined
              }
              className="flex-1 min-w-0 bg-transparent outline-none text-sm placeholder:text-[var(--color-text-muted)]"
              onClick={(e) => e.stopPropagation()}
            />
          </>
        ) : (
          <span
            className={clsx(
              'flex-1 min-w-0 truncate text-sm leading-[22px]',
              value ? 'text-[var(--color-text)]' : 'text-[var(--color-text-muted)]'
            )}
          >
            {displayValue || placeholder}
          </span>
        )}

        <div className="flex items-center gap-1 shrink-0 ml-1">
          {clearable && value && !open && !disabled && (
            <button
              type="button"
              onClick={handleClear}
              className="p-0.5 text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors rounded"
              aria-label="Clear selection"
            >
              <X size={14} />
            </button>
          )}
          <ChevronDown
            size={16}
            className={clsx(
              'text-[var(--color-text-muted)] transition-transform',
              open && 'rotate-180'
            )}
          />
        </div>
      </div>

      {/* Dropdown */}
      {open && (
        <ul
          ref={listRef}
          id="ss-listbox"
          role="listbox"
          className="absolute z-50 mt-1 w-full max-h-60 overflow-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xl py-1"
        >
          {filtered.length === 0 ? (
            <li className="px-3 py-2.5 text-sm text-[var(--color-text-muted)] text-center">
              No matches found
            </li>
          ) : (
            filtered.map((opt, i) => {
              const isSelected = opt.value === OTHER_VALUE
                ? isOtherSelected
                : opt.value === value;
              return (
                <li
                  key={opt.value}
                  id={`ss-option-${opt.value}`}
                  role="option"
                  aria-selected={isSelected}
                  className={clsx(
                    'flex items-center justify-between px-3 py-2 cursor-pointer text-sm transition-colors',
                    i === highlightIndex && 'bg-[var(--color-surface-hover)]',
                    isSelected
                      ? 'text-[var(--color-primary)] font-medium'
                      : 'text-[var(--color-text)]'
                  )}
                  onMouseEnter={() => setHighlightIndex(i)}
                  onMouseDown={(e) => {
                    e.preventDefault(); // Prevent input blur
                    selectOption(opt);
                  }}
                >
                  <span className="truncate">{opt.label}</span>
                  {isSelected && (
                    <Check size={14} className="shrink-0 ml-2" />
                  )}
                </li>
              );
            })
          )}
        </ul>
      )}

      {/* "Other" custom text input */}
      {allowOther && isOtherSelected && (
        <input
          ref={otherInputRef}
          type="text"
          value={customText}
          onChange={(e) => {
            const v = e.target.value;
            setCustomText(v);
            onChange(v);
          }}
          placeholder={otherPlaceholder}
          disabled={disabled}
          className={clsx(
            'w-full h-[38px] mt-1.5 px-3 rounded-lg border text-sm transition-colors',
            'bg-[var(--color-surface)] text-[var(--color-text)]',
            'placeholder:text-[var(--color-text-muted)]',
            'focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50 focus:border-[var(--color-primary)]',
            'border-[var(--color-border)]'
          )}
        />
      )}

      {error && <p className="mt-1 text-xs text-[var(--color-danger)]">{error}</p>}
    </div>
  );
}
