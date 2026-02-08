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
};
