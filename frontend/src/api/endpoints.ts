import api from './client';

// ── Auth ───────────────────────────────────────
export const authApi = {
  register: (data: { email: string; password: string; first_name: string; last_name: string; phone?: string }) =>
    api.post('/auth/register', data),
  login: (data: { email: string; password: string }) =>
    api.post('/auth/login', data),
  getMe: () => api.get('/auth/me'),
};

// ── Loans ──────────────────────────────────────
export const loanApi = {
  getProfile: () => api.get('/loans/profile'),
  updateProfile: (data: Record<string, unknown>) => api.put('/loans/profile', data),
  create: (data: { amount_requested: number; term_months: number; purpose: string; purpose_description?: string }) =>
    api.post('/loans/', data),
  list: () => api.get('/loans/'),
  get: (id: number) => api.get(`/loans/${id}`),
  update: (id: number, data: Record<string, unknown>) => api.put(`/loans/${id}`, data),
  submit: (id: number) => api.post(`/loans/${id}/submit`),
  uploadDocument: (id: number, formData: FormData) =>
    api.post(`/loans/${id}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  listDocuments: (id: number) => api.get(`/loans/${id}/documents`),
  // Counterproposal
  acceptCounterproposal: (id: number) => api.post(`/loans/${id}/accept-counterproposal`),
  rejectCounterproposal: (id: number) => api.post(`/loans/${id}/reject-counterproposal`),
  // Offer
  acceptOffer: (id: number) => api.post(`/loans/${id}/accept-offer`),
  declineOffer: (id: number) => api.post(`/loans/${id}/decline-offer`),
  // Contract
  signContract: (id: number, data: { signature_data: string; typed_name: string; agreed: boolean }) =>
    api.post(`/loans/${id}/sign-contract`, data),
};

// ── Underwriter ────────────────────────────────
export const underwriterApi = {
  getQueue: (status?: string) =>
    api.get('/underwriter/queue', { params: status ? { status_filter: status } : {} }),
  getApplication: (id: number) => api.get(`/underwriter/applications/${id}`),
  getFullApplication: (id: number) => api.get(`/underwriter/applications/${id}/full`),
  getDecision: (id: number) => api.get(`/underwriter/applications/${id}/decision`),
  getAuditLog: (id: number) => api.get(`/underwriter/applications/${id}/audit`),
  assign: (id: number) => api.post(`/underwriter/applications/${id}/assign`),
  decide: (id: number, data: { action: string; reason: string; approved_amount?: number; approved_rate?: number }) =>
    api.post(`/underwriter/applications/${id}/decide`, data),
  editApplication: (id: number, data: Record<string, unknown>) =>
    api.patch(`/underwriter/applications/${id}/edit`, data),
  counterpropose: (id: number, data: { proposed_amount: number; proposed_rate: number; proposed_term: number; reason: string }) =>
    api.post(`/underwriter/applications/${id}/counterpropose`, data),
  // Loan Book
  getLoanBook: (status?: string) =>
    api.get('/underwriter/loans', { params: status ? { status } : {} }),
  // Credit Bureau
  getCreditReport: (id: number) => api.get(`/underwriter/applications/${id}/credit-report`),
  downloadCreditReport: (id: number) =>
    api.get(`/underwriter/applications/${id}/credit-report/download`, { responseType: 'blob' }),
  // Staff create
  createOnBehalf: (data: Record<string, unknown>) =>
    api.post('/underwriter/applications/create-on-behalf', data),
};

// ── Verification ───────────────────────────────
export const verificationApi = {
  verify: (data: { national_id: string; document_type: string; document_id: number }) =>
    api.post('/verification/verify', data),
  getStatus: () => api.get('/verification/status'),
};

// ── Reports ────────────────────────────────────
export const reportsApi = {
  getDashboard: () => api.get('/reports/dashboard'),
  exportLoanBook: () => api.get('/reports/export/loan-book', { responseType: 'blob' }),
  getReportTypes: () => api.get('/reports/types'),
  generateReport: (reportType: string, params: { date_from?: string; date_to?: string; application_id?: number }) =>
    api.post(`/reports/generate/${reportType}`, params),
  getHistory: () => api.get('/reports/history'),
  downloadHistorical: (id: number) =>
    api.get(`/reports/history/${id}/download`, { responseType: 'blob' }),
};

// ── Payments ───────────────────────────────────
export const paymentsApi = {
  recordPayment: (appId: number, data: { amount: number; payment_type: string; payment_date: string; reference_number?: string; notes?: string }) =>
    api.post(`/payments/${appId}/record`, data),
  getHistory: (appId: number) => api.get(`/payments/${appId}/history`),
  getSchedule: (appId: number) => api.get(`/payments/${appId}/schedule`),
  payOnline: (appId: number, data: { amount: number }) =>
    api.post(`/payments/${appId}/pay-online`, data),
};

// ── Collections ────────────────────────────────
export const collectionsApi = {
  getQueue: () => api.get('/collections/queue'),
  getHistory: (appId: number) => api.get(`/collections/${appId}/history`),
  addRecord: (appId: number, data: Record<string, unknown>) =>
    api.post(`/collections/${appId}/record`, data),
  getChat: (appId: number) => api.get(`/collections/${appId}/chat`),
  sendWhatsApp: (appId: number, data: { message: string }) =>
    api.post(`/collections/${appId}/send-whatsapp`, data),
};
