import api from './client';

// ── Auth ───────────────────────────────────────
export const authApi = {
  register: (data: { email: string; password: string; first_name: string; last_name: string; phone?: string }) =>
    api.post('/auth/register', data),
  login: (data: { email: string; password: string }) =>
    api.post('/auth/login', data),
  getMe: () => api.get('/auth/me'),
  updateMe: (data: { first_name?: string; last_name?: string; phone?: string }) =>
    api.patch('/auth/me', data),
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
  downloadDocument: (appId: number, docId: number) =>
    api.get(`/loans/${appId}/documents/${docId}/download`, { responseType: 'blob' }),
  deleteDocument: (appId: number, docId: number) => api.delete(`/loans/${appId}/documents/${docId}`),
  // Counterproposal
  acceptCounterproposal: (id: number) => api.post(`/loans/${id}/accept-counterproposal`),
  rejectCounterproposal: (id: number) => api.post(`/loans/${id}/reject-counterproposal`),
  // Offer
  acceptOffer: (id: number) => api.post(`/loans/${id}/accept-offer`),
  declineOffer: (id: number) => api.post(`/loans/${id}/decline-offer`),
  // Contract
  signContract: (id: number, data: { signature_data: string; typed_name: string; agreed: boolean }) =>
    api.post(`/loans/${id}/sign-contract`, data),
  submitWithConsent: (id: number, data: { signature_data: string; typed_name: string; agreed: boolean }) =>
    api.post(`/loans/${id}/submit-with-consent`, data),
  getConsentPdf: (id: number) =>
    api.get(`/loans/${id}/consent-pdf`, { responseType: 'blob' }),
  // ID parsing (OCR)
  parseId: (formData: FormData) =>
    api.post('/loans/parse-id', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  // Comments (consumer ↔ underwriter)
  listComments: (id: number) => api.get(`/loans/${id}/comments`),
  addComment: (id: number, content: string) =>
    api.post(`/loans/${id}/comments`, { content }),
  markCommentsRead: (id: number) => api.post(`/loans/${id}/comments/mark-read`),
  // References
  listReferences: (id: number) => api.get(`/loans/${id}/references`),
  addReference: (id: number, data: { name: string; relationship_type: string; phone: string; address: string; directions?: string }) =>
    api.post(`/loans/${id}/references`, data),
  updateReference: (appId: number, refId: number, data: { name: string; relationship_type: string; phone: string; address: string; directions?: string }) =>
    api.put(`/loans/${appId}/references/${refId}`, data),
  deleteReference: (appId: number, refId: number) =>
    api.delete(`/loans/${appId}/references/${refId}`),
  // Notifications
  getNotifications: () => api.get('/loans/notifications/messages'),
  markAllNotificationsRead: () => api.post('/loans/notifications/mark-read'),
  // Collection messages (consumer-facing)
  getCollectionMessages: () => api.get('/loans/notifications/collection-messages'),
  getAppCollectionMessages: (id: number) => api.get(`/loans/${id}/collection-messages`),
};

// ── Underwriter ────────────────────────────────
export const underwriterApi = {
  getQueue: (status?: string) =>
    api.get('/underwriter/queue', { params: status ? { status_filter: status } : {} }),
  getApplication: (id: number) => api.get(`/underwriter/applications/${id}`),
  getFullApplication: (id: number) => api.get(`/underwriter/applications/${id}/full`),
  uploadDocument: (id: number, formData: FormData) =>
    api.post(`/underwriter/applications/${id}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  downloadDocument: (appId: number, docId: number) =>
    api.get(`/underwriter/applications/${appId}/documents/${docId}/download`, { responseType: 'blob' }),
  deleteDocument: (appId: number, docId: number) =>
    api.delete(`/underwriter/applications/${appId}/documents/${docId}`),
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
  // Disbursement
  disburse: (id: number, data: { method?: string; notes?: string; recipient_account_name?: string; recipient_account_number?: string; recipient_bank?: string; recipient_bank_branch?: string }) =>
    api.post(`/underwriter/applications/${id}/disburse`, data),
  getDisbursement: (id: number) =>
    api.get(`/underwriter/applications/${id}/disbursement`),
  // Loan Book
  getLoanBook: (status?: string) =>
    api.get('/underwriter/loans', { params: status ? { status } : {} }),
  // Credit Bureau
  getCreditReport: (id: number) => api.get(`/underwriter/applications/${id}/credit-report`),
  downloadCreditReport: (id: number) =>
    api.get(`/underwriter/applications/${id}/credit-report/download`, { responseType: 'blob' }),
  // Generate contract PDF
  generateContract: (id: number) =>
    api.get(`/underwriter/applications/${id}/generate-contract`, { responseType: 'blob' }),
  // Customer search
  searchCustomers: (q: string) =>
    api.get('/underwriter/customers/search', { params: { q } }),
  // Application notes
  listNotes: (id: number) =>
    api.get(`/underwriter/applications/${id}/notes`),
  addNote: (id: number, content: string) =>
    api.post(`/underwriter/applications/${id}/notes`, { content }),
  // Staff create
  createOnBehalf: (data: Record<string, unknown>) =>
    api.post('/underwriter/applications/create-on-behalf', data),
  // ID parsing (OCR)
  parseId: (formData: FormData) =>
    api.post('/underwriter/parse-id', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  // Bank statement analysis
  analyzeBankStatement: (appId: number, documentId?: number) =>
    api.post(`/underwriter/applications/${appId}/analyze-bank-statement`, null, {
      params: documentId ? { document_id: documentId } : {},
    }),
  getBankAnalysis: (appId: number) =>
    api.get(`/underwriter/applications/${appId}/bank-analysis`),
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
  getMyLoansSummary: () => api.get('/payments/summary/my-loans'),
};

// ── Collections ────────────────────────────────
export const collectionsApi = {
  // Queue
  getQueue: (params?: Record<string, unknown>) => api.get('/collections/queue', { params }),
  exportCsv: () => api.get('/collections/export-csv', { responseType: 'blob' }),
  syncCases: () => api.post('/collections/sync-cases'),
  // Cases
  listCases: (params?: Record<string, unknown>) => api.get('/collections/cases', { params }),
  getCase: (caseId: number) => api.get(`/collections/cases/${caseId}`),
  updateCase: (caseId: number, data: Record<string, unknown>) => api.patch(`/collections/cases/${caseId}`, data),
  bulkAssign: (data: { case_ids: number[]; agent_id: number }) => api.post('/collections/cases/bulk-assign', data),
  overrideNba: (caseId: number, data: { action: string; reason: string }) =>
    api.post(`/collections/cases/${caseId}/nba-override`, data),
  // PTP
  createPtp: (caseId: number, data: Record<string, unknown>) => api.post(`/collections/cases/${caseId}/ptp`, data),
  listPtps: (caseId: number) => api.get(`/collections/cases/${caseId}/ptps`),
  updatePtp: (ptpId: number, data: Record<string, unknown>) => api.patch(`/collections/ptps/${ptpId}`, data),
  // Settlements
  createSettlement: (caseId: number, data: Record<string, unknown>) =>
    api.post(`/collections/cases/${caseId}/settlement`, data),
  listSettlements: (caseId: number) => api.get(`/collections/cases/${caseId}/settlements`),
  approveSettlement: (settlementId: number) => api.patch(`/collections/settlements/${settlementId}/approve`),
  acceptSettlement: (settlementId: number) => api.patch(`/collections/settlements/${settlementId}/accept`),
  // Dashboard
  getDashboard: (periodDays?: number) => api.get('/collections/dashboard', { params: { period_days: periodDays || 30 } }),
  getAgentPerformance: () => api.get('/collections/dashboard/agent-performance'),
  // Compliance
  listComplianceRules: () => api.get('/collections/compliance-rules'),
  createComplianceRule: (data: Record<string, unknown>) => api.post('/collections/compliance-rules', data),
  checkCompliance: (data: { case_id: number; jurisdiction?: string }) =>
    api.post('/collections/check-compliance', data),
  // Legacy
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

  // Categories (per merchant)
  getCategories: (merchantId: number) => api.get(`/admin/merchants/${merchantId}/categories`),
  createCategory: (merchantId: number, data: { name: string }) =>
    api.post(`/admin/merchants/${merchantId}/categories`, data),
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

  // Rules management
  getRules: () => api.get('/admin/rules'),
  updateRules: (data: { rules: Array<Record<string, unknown>> }) => api.put('/admin/rules', data),
  deleteRule: (ruleId: string) => api.delete(`/admin/rules/${ruleId}`),
  generateRule: (data: { prompt: string; conversation_history?: Array<Record<string, string>> }) =>
    api.post('/admin/rules/generate', data),
};

// ── Conversations (Customer Support) ─────────────
export const conversationsApi = {
  create: (data?: { channel?: string; entry_point?: string; entry_context?: Record<string, unknown> }) =>
    api.post('/conversations/', data ?? {}),
  get: (id: number) => api.get(`/conversations/${id}`),
  sendMessage: (id: number, content: string) =>
    api.post(`/conversations/${id}/messages`, { content }),
  startApplication: (id: number, data: { amount_requested: number; term_months: number; purpose?: string }) =>
    api.post(`/conversations/${id}/start-application`, data),
  list: (statusFilter?: string) =>
    api.get('/conversations/', { params: statusFilter ? { status_filter: statusFilter } : {} }),
};

// ── Customer 360 ────────────────────────────────
export const customerApi = {
  get360: (userId: number) => api.get(`/customers/${userId}/360`),
  getTimeline: (userId: number, params?: { categories?: string; search?: string; offset?: number; limit?: number }) =>
    api.get(`/customers/${userId}/timeline`, { params }),
  getAiSummary: (userId: number) => api.post(`/customers/${userId}/ai-summary`),
  askAi: (userId: number, data: { question: string; history?: Array<{ role: string; content: string }> }) =>
    api.post(`/customers/${userId}/ask-ai`, data),
  getAlerts: (userId: number, statusFilter?: string) =>
    api.get(`/customers/${userId}/alerts`, { params: statusFilter ? { status_filter: statusFilter } : {} }),
  updateAlert: (userId: number, alertId: number, data: { status?: string; action_taken?: string; action_notes?: string }) =>
    api.patch(`/customers/${userId}/alerts/${alertId}`, data),
  // Staff-initiated conversations
  initiateConversation: (userId: number, data: { channel: string; message: string }) =>
    api.post(`/customers/${userId}/conversations`, data),
  staffSendMessage: (userId: number, conversationId: number, content: string) =>
    api.post(`/customers/${userId}/conversations/${conversationId}/messages`, { content }),
};

// ── Sector Analysis ─────────────────────────────
export const sectorApi = {
  getTaxonomy: () => api.get('/sector-analysis/taxonomy'),
  getDashboard: () => api.get('/sector-analysis/dashboard'),
  getSectorDetail: (sector: string) => api.get(`/sector-analysis/sectors/${encodeURIComponent(sector)}`),
  getHeatmap: () => api.get('/sector-analysis/heatmap'),
  // Policies
  getPolicies: () => api.get('/sector-analysis/policies'),
  createPolicy: (data: Record<string, unknown>) => api.post('/sector-analysis/policies', data),
  updatePolicy: (id: number, data: Record<string, unknown>) => api.patch(`/sector-analysis/policies/${id}`, data),
  approvePolicy: (id: number) => api.post(`/sector-analysis/policies/${id}/approve`),
  archivePolicy: (id: number) => api.delete(`/sector-analysis/policies/${id}`),
  // Alert rules
  getAlertRules: () => api.get('/sector-analysis/alert-rules'),
  createAlertRule: (data: Record<string, unknown>) => api.post('/sector-analysis/alert-rules', data),
  deleteAlertRule: (id: number) => api.delete(`/sector-analysis/alert-rules/${id}`),
  // Alerts
  getAlerts: (params?: { status_filter?: string; sector?: string; severity?: string }) =>
    api.get('/sector-analysis/alerts', { params }),
  updateAlert: (id: number, data: { status?: string; action_notes?: string }) =>
    api.patch(`/sector-analysis/alerts/${id}`, data),
  evaluateAlerts: () => api.post('/sector-analysis/alerts/evaluate'),
  // Macro indicators
  getMacroIndicators: (sector?: string) =>
    api.get('/sector-analysis/macro-indicators', { params: sector ? { sector } : {} }),
  createMacroIndicator: (data: Record<string, unknown>) =>
    api.post('/sector-analysis/macro-indicators', data),
  // Stress testing
  runStressTest: (data: { name: string; shocks: Record<string, unknown> }) =>
    api.post('/sector-analysis/stress-test', data),
  // Snapshots
  getSnapshots: (params?: { sector?: string; months?: number }) =>
    api.get('/sector-analysis/snapshots', { params }),
  generateSnapshot: () => api.post('/sector-analysis/snapshots/generate'),
  // Origination check
  checkOrigination: (data: { sector: string; loan_amount: number }) =>
    api.post('/sector-analysis/check-origination', data),
};

// ── Error Monitoring (Admin) ────────────────────
export const errorLogApi = {
  list: (params?: Record<string, unknown>) =>
    api.get('/error-logs', { params }),
  stats: (hours?: number) =>
    api.get('/error-logs/stats', { params: hours ? { hours } : {} }),
  get: (id: number) => api.get(`/error-logs/${id}`),
  resolve: (id: number, data?: { resolution_notes?: string }) =>
    api.patch(`/error-logs/${id}/resolve`, data || {}),
  unresolve: (id: number) =>
    api.patch(`/error-logs/${id}/unresolve`),
  bulkResolve: (ids: number[], notes?: string) =>
    api.post('/error-logs/bulk-resolve', { ids, resolution_notes: notes }),
  cleanup: (days?: number) =>
    api.delete('/error-logs/cleanup', { params: days ? { days } : {} }),
};

// ── Consumer Catalog ────────────────────────────
export const catalogApi = {
  getMerchants: () => api.get('/catalog/merchants'),
  getBranches: (merchantId: number) => api.get(`/catalog/merchants/${merchantId}/branches`),
  getCategories: (merchantId: number) => api.get(`/catalog/merchants/${merchantId}/categories`),
  getProducts: (merchantId: number, amount: number) =>
    api.get('/catalog/products', { params: { merchant_id: merchantId, amount } }),
  calculate: (data: { product_id: number; total_amount: number; term_months: number }) =>
    api.post('/catalog/calculate', data),
};
