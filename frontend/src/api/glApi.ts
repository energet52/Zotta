import api from './client';

// ── General Ledger ─────────────────────────────

export interface GLCurrency {
  id: number;
  code: string;
  name: string;
  symbol: string;
  decimal_places: number;
  is_base: boolean;
  is_active: boolean;
}

export interface GLAccount {
  id: number;
  account_code: string;
  name: string;
  description?: string;
  account_category: string;
  account_type: string;
  currency_id: number;
  parent_id?: number;
  level: number;
  is_control_account: boolean;
  is_system_account: boolean;
  status: string;
  children_count?: number;
}

export interface GLAccountBalance {
  account_id: number;
  account_code: string;
  account_name: string;
  debit_total: number;
  credit_total: number;
  balance: number;
}

export interface AccountAudit {
  id: number;
  field_changed: string;
  old_value?: string;
  new_value?: string;
  changed_by?: number;
  changed_at: string;
}

export interface JournalLine {
  id: number;
  line_number: number;
  gl_account_id: number;
  account_code?: string;
  account_name?: string;
  debit_amount: number;
  credit_amount: number;
  base_currency_amount: number;
  description?: string;
  department?: string;
  branch?: string;
  loan_reference?: string;
  tags?: Record<string, unknown>;
}

export interface JournalEntry {
  id: number;
  entry_number: string;
  transaction_date: string;
  effective_date: string;
  posting_date?: string;
  accounting_period_id?: number;
  source_type: string;
  source_reference?: string;
  description: string;
  currency_id: number;
  exchange_rate: number;
  status: string;
  total_debits: number;
  total_credits: number;
  created_by?: number;
  approved_by?: number;
  posted_by?: number;
  created_at?: string;
  approved_at?: string;
  posted_at?: string;
  reversal_of_id?: number;
  reversed_by_id?: number;
  narrative?: string;
  rejection_reason?: string;
  lines: JournalLine[];
}

export interface AccountingPeriod {
  id: number;
  fiscal_year: number;
  period_number: number;
  name: string;
  start_date: string;
  end_date: string;
  status: string;
}

export interface TrialBalanceRow {
  account_id: number;
  account_code: string;
  account_name: string;
  account_category: string;
  level: number;
  debit_balance: number;
  credit_balance: number;
}

export interface TrialBalance {
  period_id?: number;
  as_of_date?: string;
  rows: TrialBalanceRow[];
  total_debits: number;
  total_credits: number;
  is_balanced: boolean;
}

export interface LedgerTransaction {
  date: string;
  entry_number: string;
  entry_id: number;
  description: string;
  debit: number;
  credit: number;
  running_balance: number;
  source_type: string;
}

export interface AccountLedger {
  account_id: number;
  account_code: string;
  account_name: string;
  opening_balance: number;
  transactions: LedgerTransaction[];
  closing_balance: number;
}

export interface JournalLineInput {
  gl_account_id: number;
  debit_amount: number;
  credit_amount: number;
  description?: string;
  department?: string;
  branch?: string;
  loan_reference?: string;
}

export interface PaginatedEntries {
  items: JournalEntry[];
  total: number;
  page: number;
  page_size: number;
}

export const glApi = {
  // Currencies
  getCurrencies: () => api.get<GLCurrency[]>('/gl/currencies'),

  // Accounts
  getAccounts: (params?: { category?: string; status?: string; parent_id?: number; search?: string }) =>
    api.get<GLAccount[]>('/gl/accounts', { params }),
  createAccount: (data: {
    name: string; account_category: string; account_type: string;
    currency_code?: string; parent_id?: number; account_code?: string;
    description?: string; is_control_account?: boolean;
  }) => api.post<GLAccount>('/gl/accounts', data),
  updateAccount: (id: number, data: { name?: string; description?: string; is_control_account?: boolean }) =>
    api.put<GLAccount>(`/gl/accounts/${id}`, data),
  freezeAccount: (id: number) => api.post(`/gl/accounts/${id}/freeze`),
  getAccountBalance: (id: number, params?: { period_id?: number; as_of_date?: string }) =>
    api.get<GLAccountBalance>(`/gl/accounts/${id}/balance`, { params }),
  getAccountAudit: (id: number) => api.get<AccountAudit[]>(`/gl/accounts/${id}/audit`),
  getAccountLedger: (id: number, params?: { period_id?: number; date_from?: string; date_to?: string }) =>
    api.get<AccountLedger>(`/gl/accounts/${id}/ledger`, { params }),

  // Journal entries
  getEntries: (params?: {
    status?: string; source_type?: string; date_from?: string; date_to?: string;
    period_id?: number; account_id?: number; amount_min?: number; amount_max?: number;
    loan_id?: string; q?: string; entry_number?: string; page?: number; page_size?: number;
  }) => api.get<PaginatedEntries>('/gl/entries', { params }),
  createEntry: (data: {
    lines: JournalLineInput[]; description: string; source_type?: string;
    source_reference?: string; transaction_date?: string; effective_date?: string;
    currency_code?: string; exchange_rate?: number; narrative?: string;
  }) => api.post<JournalEntry>('/gl/entries', data),
  getEntry: (id: number) => api.get<JournalEntry>(`/gl/entries/${id}`),
  submitEntry: (id: number) => api.post(`/gl/entries/${id}/submit`),
  approveEntry: (id: number) => api.post(`/gl/entries/${id}/approve`),
  postEntry: (id: number) => api.post(`/gl/entries/${id}/post`),
  rejectEntry: (id: number, reason: string) => api.post(`/gl/entries/${id}/reject`, { reason }),
  reverseEntry: (id: number, data: { reason: string; effective_date?: string }) =>
    api.post<JournalEntry>(`/gl/entries/${id}/reverse`, data),

  // Trial balance
  getTrialBalance: (params?: { period_id?: number; as_of_date?: string; level?: number }) =>
    api.get<TrialBalance>('/gl/trial-balance', { params }),

  // Periods
  getPeriods: (params?: { fiscal_year?: number; status?: string }) =>
    api.get<AccountingPeriod[]>('/gl/periods', { params }),
  createFiscalYear: (year: number) => api.post<AccountingPeriod[]>('/gl/periods', { year }),
  closePeriod: (id: number) => api.post(`/gl/periods/${id}/close`),
  softClosePeriod: (id: number) => api.post(`/gl/periods/${id}/soft-close`),
  lockPeriod: (id: number) => api.post(`/gl/periods/${id}/lock`),
  reopenPeriod: (id: number) => api.post(`/gl/periods/${id}/reopen`),

  // Dashboard
  getDashboardSummary: (periodId?: number) =>
    api.get('/gl/dashboard-summary', { params: periodId ? { period_id: periodId } : {} }),

  // Anomalies (AI)
  getAnomalies: (params?: { status?: string; min_risk_score?: number; limit?: number }) =>
    api.get<GLAnomaly[]>('/gl/anomalies', { params }),
  reviewAnomaly: (id: number, action: 'reviewed' | 'dismissed') =>
    api.post(`/gl/anomalies/${id}/review`, null, { params: { action } }),

  // Natural language query
  postQuery: (data: { question: string; context?: Record<string, unknown> }) =>
    api.post<GLQueryResponse>('/gl/query', data),
};

// ── Anomaly types ─────────────────────────────

export interface GLAnomaly {
  id: number;
  journal_entry_id: number;
  anomaly_type: string;
  risk_score: number;
  explanation: string;
  status: string;
  reviewed_by: number | null;
  reviewed_at: string | null;
  created_at: string;
}

// ── Query response types ──────────────────────

export type GLQueryResponse = {
  type: 'number';
  value?: number;
  formatted?: string;
  summary?: string;
  data?: Record<string, unknown>[];
  query_used?: string;
} | {
  type: 'table';
  summary?: string;
  data?: Record<string, unknown>[];
  columns?: string[];
  query_used?: string;
} | {
  type: 'suggestion';
  message?: string;
  query_used?: string | null;
} | {
  type: 'error';
  message?: string;
  query_used?: string;
};
