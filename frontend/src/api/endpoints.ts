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
  create: (data: {
    amount_requested: number;
    term_months: number;
    purpose: string;
    purpose_description?: string;
    merchant_id?: number;
    branch_id?: number;
    credit_product_id?: number;
    downpayment?: number;
    total_financed?: number;
    items?: Array<{ category_id: number; description?: string; price: number; quantity: number }>;
  }) =>
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
  runEngine: (id: number) => api.post(`/underwriter/applications/${id}/run-engine`),
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

// ── Administration ──────────────────────────────
export const adminApi = {
  // Merchants
  getMerchants: () => api.get('/admin/merchants'),
  createMerchant: (data: { name: string; is_active?: boolean }) => api.post('/admin/merchants', data),
  updateMerchant: (id: number, data: { name?: string; is_active?: boolean }) =>
    api.put(`/admin/merchants/${id}`, data),
  deleteMerchant: (id: number) => api.delete(`/admin/merchants/${id}`),

  // Branches
  getBranches: (merchantId: number) => api.get(`/admin/merchants/${merchantId}/branches`),
  createBranch: (
    merchantId: number,
    data: { name: string; address?: string; is_online?: boolean; is_active?: boolean },
  ) => api.post(`/admin/merchants/${merchantId}/branches`, data),
  updateBranch: (
    id: number,
    data: { name?: string; address?: string; is_online?: boolean; is_active?: boolean },
  ) => api.put(`/admin/branches/${id}`, data),
  deleteBranch: (id: number) => api.delete(`/admin/branches/${id}`),

  // Categories
  getCategories: () => api.get('/admin/categories'),
  createCategory: (data: { name: string }) => api.post('/admin/categories', data),
  updateCategory: (id: number, data: { name: string }) => api.put(`/admin/categories/${id}`, data),
  deleteCategory: (id: number) => api.delete(`/admin/categories/${id}`),

  // Products
  getProducts: () => api.get('/admin/products'),
  getProduct: (id: number) => api.get(`/admin/products/${id}`),
  createProduct: (data: Record<string, unknown>) => api.post('/admin/products', data),
  updateProduct: (id: number, data: Record<string, unknown>) => api.put(`/admin/products/${id}`, data),
  deleteProduct: (id: number) => api.delete(`/admin/products/${id}`),

  // Score ranges
  createScoreRange: (productId: number, data: { min_score: number; max_score: number }) =>
    api.post(`/admin/products/${productId}/score-ranges`, data),
  updateScoreRange: (id: number, data: { min_score?: number; max_score?: number }) =>
    api.put(`/admin/score-ranges/${id}`, data),
  deleteScoreRange: (id: number) => api.delete(`/admin/score-ranges/${id}`),

  // Fees
  createFee: (
    productId: number,
    data: { fee_type: string; fee_base: string; fee_amount: number; is_available?: boolean },
  ) => api.post(`/admin/products/${productId}/fees`, data),
  updateFee: (
    id: number,
    data: { fee_type?: string; fee_base?: string; fee_amount?: number; is_available?: boolean },
  ) => api.put(`/admin/fees/${id}`, data),
  deleteFee: (id: number) => api.delete(`/admin/fees/${id}`),
};

// ── Consumer Catalog ────────────────────────────
export const catalogApi = {
  getMerchants: () => api.get('/catalog/merchants'),
  getBranches: (merchantId: number) => api.get(`/catalog/merchants/${merchantId}/branches`),
  getCategories: () => api.get('/catalog/categories'),
  getProducts: (merchantId: number, amount: number) =>
    api.get('/catalog/products', { params: { merchant_id: merchantId, amount } }),
  calculate: (data: { product_id: number; total_amount: number; term_months: number }) =>
    api.post('/catalog/calculate', data),
};
