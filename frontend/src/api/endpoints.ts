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
  // Cancel
  cancel: (id: number, reason?: string) => api.post(`/loans/${id}/cancel`, { reason }),
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
  getStaff: () => api.get('/underwriter/staff'),
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
  // Void
  voidApplication: (id: number, reason: string) =>
    api.post(`/underwriter/applications/${id}/void`, { reason }),
  // Loan Book
  getLoanBook: (status?: string) =>
    api.get('/underwriter/loans', { params: status ? { status } : {} }),
  // Credit Bureau
  getCreditReport: (id: number) => api.get(`/underwriter/applications/${id}/credit-report`),
  downloadCreditReport: (id: number) =>
    api.get(`/underwriter/applications/${id}/credit-report/download`, { responseType: 'blob' }),
  // AV Knowles Bureau (live web inquiry)
  runAVKnowlesInquiry: (id: number, data: Record<string, unknown>) =>
    api.post(`/underwriter/applications/${id}/av-knowles-inquiry`, data, { timeout: 120_000 }),
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
  getCaseFull: (caseId: number) => api.get(`/collections/cases/${caseId}/full`),
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
  // AI
  getDailyBriefing: () => api.get('/collections/daily-briefing'),
  draftMessage: (data: { case_id: number; channel: string; template_type: string }) =>
    api.post('/collections/draft-message', data),
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

// ── Scorecards ─────────────────────────────────
export const scorecardsApi = {
  // CRUD
  list: (params?: Record<string, unknown>) => api.get('/scorecards/', { params }),
  get: (id: number) => api.get(`/scorecards/${id}`),
  create: (data: Record<string, unknown>) => api.post('/scorecards/', data),
  update: (id: number, data: Record<string, unknown>) => api.put(`/scorecards/${id}`, data),
  clone: (id: number, name?: string) => api.post(`/scorecards/${id}/clone`, null, { params: name ? { name } : {} }),
  importCsv: (formData: FormData, params: Record<string, unknown>) =>
    api.post('/scorecards/import-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params,
    }),

  // Editing
  editPoints: (id: number, data: { bin_id: number; new_points: number; justification: string }) =>
    api.patch(`/scorecards/${id}/edit-points`, data),
  editBins: (id: number, data: Record<string, unknown>) =>
    api.patch(`/scorecards/${id}/edit-bins`, data),
  weightScale: (id: number, data: { characteristic_id: number; multiplier: number; justification: string }) =>
    api.patch(`/scorecards/${id}/weight-scale`, data),
  editCutoffs: (id: number, data: Record<string, unknown>) =>
    api.patch(`/scorecards/${id}/edit-cutoffs`, data),

  // Raw script
  getScript: (id: number) => api.get(`/scorecards/${id}/script`),
  saveScript: (id: number, data: { script: string; justification?: string }) =>
    api.put(`/scorecards/${id}/script`, data),
  liveCalculate: (id: number, data: Record<string, unknown>) =>
    api.post(`/scorecards/${id}/live-calculate`, data),

  // Champion-Challenger
  getChampionChallengerStatus: () => api.get('/scorecards/champion-challenger/status'),
  activateShadow: (id: number) => api.post(`/scorecards/${id}/activate-shadow`),
  activateChallenger: (id: number, trafficPct: number) =>
    api.post(`/scorecards/${id}/activate-challenger`, null, { params: { traffic_pct: trafficPct } }),
  promoteToChampion: (id: number, data: { justification: string }) =>
    api.post(`/scorecards/${id}/promote-to-champion`, data),
  killSwitch: (id: number) => api.post(`/scorecards/${id}/kill-switch`),
  retire: (id: number) => api.post(`/scorecards/${id}/retire`),
  updateTrafficAllocation: (allocations: Array<{ scorecard_id: number; traffic_pct: number }>) =>
    api.patch('/scorecards/traffic-allocation', allocations),

  // Scoring
  scoreApplication: (data: { application_id: number }) => api.post('/scorecards/score-application', data),
  getScoreResults: (applicationId: number) => api.get(`/scorecards/score-results/${applicationId}`),
  whatIf: (id: number, data: { application_id: number; modifications: Record<string, unknown> }) =>
    api.post(`/scorecards/${id}/what-if`, data),
  batchScore: (id: number, formData: FormData) =>
    api.post(`/scorecards/${id}/batch-score`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  simulateImpact: (id: number) => api.post(`/scorecards/${id}/simulate-impact`),

  // Performance
  getPerformance: (id: number) => api.get(`/scorecards/${id}/performance`),
  getComparison: () => api.get('/scorecards/comparison/champion-challenger'),
  getVintageAnalysis: (id: number, months?: number) =>
    api.get(`/scorecards/${id}/vintage-analysis`, { params: months ? { months } : {} }),
  getScoreBands: (id: number) => api.get(`/scorecards/${id}/score-bands`),
  getAlerts: (id: number) => api.get(`/scorecards/${id}/alerts`),
  runHealthCheck: (id: number) => api.post(`/scorecards/${id}/run-health-check`),
  acknowledgeAlert: (alertId: number) => api.patch(`/scorecards/alerts/${alertId}/acknowledge`),

  // Change log
  getChangeLog: (id: number) => api.get(`/scorecards/${id}/change-log`),
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

  // Rate Tiers (Risk-Based Pricing)
  createRateTier: (
    productId: number,
    data: { tier_name: string; min_score: number; max_score: number; interest_rate: number; max_ltv_pct?: number; max_dti_pct?: number; is_active?: boolean },
  ) => api.post(`/admin/products/${productId}/rate-tiers`, data),
  updateRateTier: (
    id: number,
    data: { tier_name?: string; min_score?: number; max_score?: number; interest_rate?: number; max_ltv_pct?: number; max_dti_pct?: number; is_active?: boolean },
  ) => api.put(`/admin/rate-tiers/${id}`, data),
  deleteRateTier: (id: number) => api.delete(`/admin/rate-tiers/${id}`),

  // Product Cloning
  cloneProduct: (id: number) => api.post(`/admin/products/${id}/clone`),

  // Product Analytics & AI
  getProductAnalytics: (id: number) => api.get(`/admin/products/${id}/analytics`),
  getPortfolioOverview: () => api.get('/admin/products/portfolio/overview'),
  productAdvisor: (data: { product_id?: number; question: string; conversation_history?: Array<Record<string, string>> }) =>
    api.post('/admin/products/ai/advisor', data),
  productSimulate: (data: { product_id: number; changes: Record<string, unknown> }) =>
    api.post('/admin/products/ai/simulate', data),
  productGenerate: (data: { description: string }) =>
    api.post('/admin/products/ai/generate', data),
  productCompare: (data: { product_ids: number[] }) =>
    api.post('/admin/products/ai/compare', data),

  // Rules management
  getRules: () => api.get('/admin/rules'),
  updateRules: (data: { rules: Array<Record<string, unknown>> }) => api.put('/admin/rules', data),
  deleteRule: (ruleId: string) => api.delete(`/admin/rules/${ruleId}`),
  generateRule: (data: { prompt: string; conversation_history?: Array<Record<string, string>> }) =>
    api.post('/admin/rules/generate', data),

  // Rules history, stats & AI analysis
  getRulesHistory: (params?: { limit?: number; offset?: number }) =>
    api.get('/admin/rules/history', { params }),
  getRulesStats: () => api.get('/admin/rules/stats'),
  analyzeRules: () => api.post('/admin/rules/ai/analyze'),

  // Audit Trail
  getAuditTrail: (params?: Record<string, string | number | undefined>) =>
    api.get('/admin/audit-trail', { params }),
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
  // Contact info update
  updateContact: (userId: number, data: Record<string, string>) =>
    api.patch(`/customers/${userId}/contact`, data),
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

// ── User Management ─────────────────────────────
export const userApi = {
  list: (params?: Record<string, unknown>) =>
    api.get('/users/', { params }),
  count: () => api.get('/users/count'),
  get: (id: number) => api.get(`/users/${id}`),
  create: (data: Record<string, unknown>) => api.post('/users/', data),
  update: (id: number, data: Record<string, unknown>) => api.patch(`/users/${id}`, data),
  suspend: (id: number) => api.post(`/users/${id}/suspend`),
  reactivate: (id: number) => api.post(`/users/${id}/reactivate`),
  deactivate: (id: number) => api.post(`/users/${id}/deactivate`),
  unlock: (id: number) => api.post(`/users/${id}/unlock`),
  resetPassword: (id: number, data: { new_password: string }) =>
    api.post(`/users/${id}/reset-password`, data),
  // Roles
  getUserRoles: (userId: number) => api.get(`/users/${userId}/roles`),
  assignRoles: (userId: number, data: { role_ids: number[] }) =>
    api.put(`/users/${userId}/roles`, data),
  listRoles: () => api.get('/users/roles/all'),
  getRole: (id: number) => api.get(`/users/roles/${id}`),
  createRole: (data: Record<string, unknown>) => api.post('/users/roles', data),
  updateRole: (id: number, data: Record<string, unknown>) => api.patch(`/users/roles/${id}`, data),
  deleteRole: (id: number, reassignToRoleId: number) =>
    api.delete(`/users/roles/${id}?reassign_to_role_id=${reassignToRoleId}`),
  deleteUser: (id: number) => api.delete(`/users/${id}`),
  listPermissions: () => api.get('/users/permissions/all'),
  // Sessions
  getUserSessions: (userId: number) => api.get(`/users/${userId}/sessions`),
  revokeAllSessions: (userId: number) => api.post(`/users/${userId}/sessions/revoke-all`),
  // Login history
  getLoginHistory: (userId: number, limit?: number) =>
    api.get(`/users/${userId}/login-history`, { params: limit ? { limit } : {} }),
  // Pending actions
  listPendingActions: () => api.get('/users/pending-actions'),
  decidePendingAction: (id: number, data: { approved: boolean; rejection_reason?: string }) =>
    api.post(`/users/pending-actions/${id}/decide`, data),
  // Auth extensions
  mySessions: () => api.get('/auth/sessions'),
  revokeSession: (sessionId: number) => api.delete(`/auth/sessions/${sessionId}`),
  setupMFA: () => api.post('/auth/mfa/setup'),
  confirmMFA: (data: { code: string; mfa_token?: string }) => api.post('/auth/mfa/confirm', data),
  verifyMFA: (data: { code: string; mfa_token: string }) => api.post('/auth/mfa/verify', data),
  disableMFA: () => api.delete('/auth/mfa/disable'),
  changePassword: (data: { old_password: string; new_password: string }) =>
    api.post('/auth/change-password', data),
};

// ── Collection Sequences ────────────────────────
export const sequencesApi = {
  // Sequences
  listSequences: (params?: Record<string, unknown>) =>
    api.get('/admin/collection-sequences/sequences', { params }),
  createSequence: (data: Record<string, unknown>) =>
    api.post('/admin/collection-sequences/sequences', data),
  getSequence: (id: number) =>
    api.get(`/admin/collection-sequences/sequences/${id}`),
  updateSequence: (id: number, data: Record<string, unknown>) =>
    api.put(`/admin/collection-sequences/sequences/${id}`, data),
  deleteSequence: (id: number) =>
    api.delete(`/admin/collection-sequences/sequences/${id}`),
  duplicateSequence: (id: number) =>
    api.post(`/admin/collection-sequences/sequences/${id}/duplicate`),

  // Steps
  addStep: (sequenceId: number, data: Record<string, unknown>) =>
    api.post(`/admin/collection-sequences/sequences/${sequenceId}/steps`, data),
  updateStep: (stepId: number, data: Record<string, unknown>) =>
    api.put(`/admin/collection-sequences/steps/${stepId}`, data),
  deleteStep: (stepId: number) =>
    api.delete(`/admin/collection-sequences/steps/${stepId}`),
  reorderSteps: (sequenceId: number, data: { step_ids: number[] }) =>
    api.put(`/admin/collection-sequences/sequences/${sequenceId}/reorder-steps`, data),

  // Templates
  listTemplates: (params?: Record<string, unknown>) =>
    api.get('/admin/collection-sequences/templates', { params }),
  createTemplate: (data: Record<string, unknown>) =>
    api.post('/admin/collection-sequences/templates', data),
  updateTemplate: (id: number, data: Record<string, unknown>) =>
    api.put(`/admin/collection-sequences/templates/${id}`, data),
  deleteTemplate: (id: number) =>
    api.delete(`/admin/collection-sequences/templates/${id}`),

  // Enrollments
  listEnrollments: (params?: Record<string, unknown>) =>
    api.get('/admin/collection-sequences/enrollments', { params }),
  createEnrollment: (data: { case_id: number; sequence_id: number }) =>
    api.post('/admin/collection-sequences/enrollments', data),
  updateEnrollment: (id: number, data: Record<string, unknown>) =>
    api.patch(`/admin/collection-sequences/enrollments/${id}`, data),
  autoEnroll: () =>
    api.post('/admin/collection-sequences/enrollments/auto-enroll'),
  getEnrollmentTimeline: (id: number) =>
    api.get(`/admin/collection-sequences/enrollments/${id}/timeline`),

  // AI
  generateSequence: (data: { description: string; delinquency_stage: string }) =>
    api.post('/admin/collection-sequences/ai/generate-sequence', data),
  optimizeSequence: (data: { sequence_id: number }) =>
    api.post('/admin/collection-sequences/ai/optimize-sequence', data),
  generateTemplate: (data: { channel: string; tone: string; category: string; context?: string }) =>
    api.post('/admin/collection-sequences/ai/generate-template', data),
  previewMessage: (data: { body: string; context?: Record<string, string> }) =>
    api.post('/admin/collection-sequences/ai/preview-message', data),

  // Analytics
  getAnalytics: () =>
    api.get('/admin/collection-sequences/analytics'),
  getSequenceAnalytics: (id: number) =>
    api.get(`/admin/collection-sequences/sequences/${id}/analytics`),
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

// ── Queue Management ──────────────────────────────
export const queueApi = {
  // Core queue
  getSharedQueue: (params?: Record<string, unknown>) => api.get('/queue/shared', { params }),
  getMyQueue: () => api.get('/queue/my-queue'),
  getWaiting: () => api.get('/queue/waiting'),
  claimEntry: (entryId: number) => api.post(`/queue/${entryId}/claim`),
  releaseEntry: (entryId: number) => api.post(`/queue/${entryId}/release`),
  returnToBorrower: (entryId: number, data: { reason: string }) => api.post(`/queue/${entryId}/return-to-borrower`, data),
  borrowerResponded: (entryId: number) => api.post(`/queue/${entryId}/borrower-responded`),
  explainPriority: (entryId: number) => api.get(`/queue/${entryId}/explain`),
  getTimeline: (entryId: number) => api.get(`/queue/${entryId}/timeline`),
  getAwareness: () => api.get('/queue/awareness'),

  // Stages
  advanceStage: (entryId: number, data?: { stage_slug?: string }) => api.post(`/queue/${entryId}/advance`, data || {}),
  returnToStage: (entryId: number, data: { stage_slug: string; reason: string }) => api.post(`/queue/${entryId}/return-to-stage`, data),
  getPipeline: () => api.get('/queue/pipeline'),

  // Assignment
  assignEntry: (entryId: number, userId: number) => api.post(`/queue/${entryId}/assign/${userId}`),
  reassignEntry: (entryId: number, userId: number) => api.post(`/queue/${entryId}/reassign/${userId}`),
  deferEntry: (entryId: number) => api.post(`/queue/${entryId}/defer`),
  triggerRebalance: () => api.post('/queue/rebalance'),
  explainAssignment: (entryId: number) => api.get(`/queue/${entryId}/explain-assignment`),

  // Staff
  listStaff: () => api.get('/queue/staff'),
  updateStaffProfile: (userId: number, data: Record<string, unknown>) => api.put(`/queue/staff/${userId}/profile`, data),
  needHelp: (userId: number) => api.post(`/queue/staff/${userId}/need-help`),

  // Config
  getConfig: () => api.get('/queue/config'),
  updateConfig: (data: Record<string, unknown>) => api.put('/queue/config', data),
  listStages: () => api.get('/queue/config/stages'),
  createStage: (data: Record<string, unknown>) => api.post('/queue/config/stages', data),
  updateStage: (stageId: number, data: Record<string, unknown>) => api.put(`/queue/config/stages/${stageId}`, data),
  deleteStage: (stageId: number) => api.delete(`/queue/config/stages/${stageId}`),

  // Exceptions
  listExceptions: (params?: Record<string, unknown>) => api.get('/queue/exceptions', { params }),
  createException: (entryId: number, data: Record<string, unknown>) => api.post('/queue/exceptions', data, { params: { entry_id: entryId } }),
  resolveException: (exceptionId: number, data: { status: string; notes?: string }) => api.post(`/queue/exceptions/${exceptionId}/resolve`, data),
  getExceptionPrecedent: (exceptionId: number) => api.get(`/queue/exceptions/${exceptionId}/precedent`),

  // Analytics
  getAmbientAnalytics: () => api.get('/queue/analytics/ambient'),
  getThroughputAnalytics: (days?: number) => api.get('/queue/analytics/throughput', { params: days ? { days } : {} }),
  getTeamAnalytics: () => api.get('/queue/analytics/team'),
  getInsights: () => api.get('/queue/analytics/insights'),
};

// ── Pre-Approval ────────────────────────────────────────────────
export const preApprovalApi = {
  parsePriceTag: (formData: FormData) => api.post('/pre-approval/parse-price-tag', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  searchMerchants: (q?: string) => api.get('/pre-approval/merchants', { params: { q: q || '' } }),
  getMerchantBranches: (merchantId: number) => api.get(`/pre-approval/merchants/${merchantId}/branches`),
  checkLimits: (amount: number, merchantId?: number) => api.get('/pre-approval/products/check-limits', { params: { amount, merchant_id: merchantId } }),
  start: (data: Record<string, unknown>) => api.post('/pre-approval/start', data),
  sendOTP: (ref: string) => api.post(`/pre-approval/${ref}/send-otp`),
  verifyOTP: (ref: string, code: string) => api.post(`/pre-approval/${ref}/verify-otp`, { code }),
  getStatus: (ref: string, phone: string) => api.get(`/pre-approval/${ref}/status`, { params: { phone } }),
  getDocumentChecklist: (ref: string) => api.get(`/pre-approval/${ref}/document-checklist`),
  checkLowerAmount: (ref: string, amount: number) => api.post(`/pre-approval/${ref}/check-lower-amount`, { amount }),
  convert: (ref: string) => api.post(`/pre-approval/${ref}/convert`),
  // Admin
  adminList: (params?: Record<string, unknown>) => api.get('/pre-approval/admin/list', { params }),
  adminAnalytics: (days?: number) => api.get('/pre-approval/admin/analytics', { params: { days: days || 30 } }),
  adminReferred: () => api.get('/pre-approval/admin/referred'),
  adminDetail: (ref: string) => api.get(`/pre-approval/admin/${ref}`),
  adminDecide: (ref: string, data: { outcome: string; reason?: string }) => api.post(`/pre-approval/admin/${ref}/decide`, data),
};

// ── Decision Strategy Management ─────────────────────────────────
export const strategyApi = {
  list: (params?: Record<string, unknown>) => api.get('/strategies', { params }),
  create: (data: Record<string, unknown>) => api.post('/strategies', data),
  get: (id: number) => api.get(`/strategies/${id}`),
  update: (id: number, data: Record<string, unknown>) => api.put(`/strategies/${id}`, data),
  activate: (id: number, emergency?: boolean) =>
    api.post(`/strategies/${id}/activate`, null, { params: emergency ? { emergency: true } : {} }),
  archive: (id: number) => api.post(`/strategies/${id}/archive`),
  versions: (id: number) => api.get(`/strategies/${id}/versions`),
};

export const decisionTreeApi = {
  list: (params?: Record<string, unknown>) => api.get('/decision-trees', { params }),
  create: (data: Record<string, unknown>) => api.post('/decision-trees', data),
  get: (id: number) => api.get(`/decision-trees/${id}`),
  update: (id: number, data: Record<string, unknown>) => api.put(`/decision-trees/${id}`, data),
  validate: (id: number) => api.post(`/decision-trees/${id}/validate`),
  activate: (id: number) => api.post(`/decision-trees/${id}/activate`),
  versions: (id: number) => api.get(`/decision-trees/${id}/versions`),
};

export const championChallengerApi = {
  start: (data: Record<string, unknown>) => api.post('/champion-challenger', data),
  get: (id: number) => api.get(`/champion-challenger/${id}`),
  promote: (id: number) => api.post(`/champion-challenger/${id}/promote`),
  discard: (id: number) => api.delete(`/champion-challenger/${id}`),
};

export const simulationApi = {
  replay: (data: Record<string, unknown>) => api.post('/simulation/replay', data),
  trace: (data: Record<string, unknown>) => api.post('/simulation/trace', data),
  impact: (data: Record<string, unknown>) => api.post('/simulation/impact', data),
};

export const decisionExplanationApi = {
  get: (decisionId: number) => api.get(`/decisions/${decisionId}/explanation`),
};
