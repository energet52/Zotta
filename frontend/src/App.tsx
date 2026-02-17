import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/authStore';

// Layouts
import ConsumerLayout from './components/layout/ConsumerLayout';
import BackOfficeLayout from './components/layout/BackOfficeLayout';

// Consumer pages
import Login from './apps/consumer/pages/Login';
import Register from './apps/consumer/pages/Register';
import Dashboard from './apps/consumer/pages/Dashboard';
import LoanApplication from './apps/consumer/pages/LoanApplication';
import ApplicationStatus from './apps/consumer/pages/ApplicationStatus';
import Chat from './apps/consumer/pages/Chat';
import Profile from './apps/consumer/pages/Profile';
import MyLoans from './apps/consumer/pages/MyLoans.tsx';
import Notifications from './apps/consumer/pages/Notifications';
import PreApproval from './apps/consumer/pages/PreApproval';
import PreApprovalStatus from './apps/consumer/pages/PreApprovalStatus';

// Back-office pages
import UnderwriterDashboard from './apps/backoffice/pages/UnderwriterDashboard';
import ApplicationReview from './apps/backoffice/pages/ApplicationReview';
import Reports from './apps/backoffice/pages/Reports';
import ConversationQueue from './apps/backoffice/pages/ConversationQueue';
import ConversationDetail from './apps/backoffice/pages/ConversationDetail';
import LoanBook from './apps/backoffice/pages/LoanBook';
import Collections from './apps/backoffice/pages/Collections';
import CollectionDetail from './apps/backoffice/pages/CollectionDetail';
import CollectionsDashboard from './apps/backoffice/pages/CollectionsDashboard';
import CollectionSequences from './apps/backoffice/pages/CollectionSequences';
import NewApplication from './apps/backoffice/pages/NewApplication';
import ProductManagement from './apps/backoffice/pages/ProductManagement';
import ProductDetail from './apps/backoffice/pages/ProductDetail';
import MerchantManagement from './apps/backoffice/pages/MerchantManagement';
import RulesManagement from './apps/backoffice/pages/RulesManagement';
import CustomerList from './apps/backoffice/pages/CustomerList';
import Customer360 from './apps/backoffice/pages/Customer360';
import SmartQueue from './apps/backoffice/pages/SmartQueue';
import QueueConfigPage from './apps/backoffice/pages/QueueConfig';
import QueueAnalytics from './apps/backoffice/pages/QueueAnalytics';

// Scorecard pages
import ScorecardManagement from './apps/backoffice/pages/ScorecardManagement';
import ScorecardDetail, { CreateScorecardForm } from './apps/backoffice/pages/ScorecardDetail';

// Sector Analysis pages
import SectorDashboard from './apps/backoffice/pages/sector/SectorDashboard';
import SectorDetail from './apps/backoffice/pages/sector/SectorDetail';
import SectorPolicies from './apps/backoffice/pages/sector/SectorPolicies';

// GL pages
import GLDashboard from './apps/backoffice/pages/gl/GLDashboard';
import GLChartOfAccounts from './apps/backoffice/pages/gl/ChartOfAccounts';
import GLJournalEntries from './apps/backoffice/pages/gl/JournalEntries';
import BalanceSheet from './apps/backoffice/pages/gl/BalanceSheet';
import IncomeStatement from './apps/backoffice/pages/gl/IncomeStatement';
import GLAccountLedger from './apps/backoffice/pages/gl/AccountLedger';
import GLTrialBalance from './apps/backoffice/pages/gl/TrialBalance';
import GLAccountingPeriods from './apps/backoffice/pages/gl/AccountingPeriods';
import GLMappings from './apps/backoffice/pages/gl/GLMappings';
import GLReports from './apps/backoffice/pages/gl/GLReports';
import ReportBuilder from './apps/backoffice/pages/gl/ReportBuilder';
import AnomalyDashboard from './apps/backoffice/pages/gl/AnomalyDashboard';
import GLChat from './apps/backoffice/pages/gl/GLChat';

// User Management pages
import UserManagement from './apps/backoffice/pages/UserManagement';
import UserDetail, { CreateUserForm } from './apps/backoffice/pages/UserDetail';
import RoleEditor, { RoleDetailPage } from './apps/backoffice/pages/RoleEditor';

// Pre-Approval backoffice
import PreApprovalDashboard from './apps/backoffice/pages/PreApprovalDashboard';
import PreApprovalDetail from './apps/backoffice/pages/PreApprovalDetail';

// Admin pages
import ErrorMonitor from './apps/backoffice/pages/ErrorMonitor';
import AuditTrail from './apps/backoffice/pages/AuditTrail';

function ProtectedRoute({ children, allowedRoles }: { children: React.ReactNode; allowedRoles?: string[] }) {
  const { isAuthenticated, user, isLoading } = useAuthStore();

  if (isLoading) {
    return <div className="min-h-screen flex items-center justify-center text-gray-400">Loading...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return <Navigate to={user.role === 'applicant' ? '/dashboard' : '/backoffice'} replace />;
  }

  return <>{children}</>;
}

export default function App() {
  const { loadUser, isAuthenticated } = useAuthStore();

  useEffect(() => {
    if (isAuthenticated) {
      loadUser();
    }
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/pre-approval" element={<PreApproval />} />
        <Route path="/pre-approval/status" element={<PreApprovalStatus />} />
        <Route path="/pre-approval/status/:ref" element={<PreApprovalStatus />} />

        {/* Consumer portal */}
        <Route
          element={
            <ProtectedRoute allowedRoles={['applicant']}>
              <ConsumerLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/apply" element={<LoanApplication />} />
          <Route path="/loans" element={<MyLoans />} />
          <Route path="/applications" element={<Dashboard />} />
          <Route path="/applications/:id" element={<ApplicationStatus />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/notifications" element={<Notifications />} />
          <Route path="/profile" element={<Profile />} />
        </Route>

        {/* Back-office portal */}
        <Route
          element={
            <ProtectedRoute allowedRoles={['admin', 'senior_underwriter', 'junior_underwriter']}>
              <BackOfficeLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/backoffice" element={<UnderwriterDashboard />} />
          <Route path="/backoffice/conversations" element={<ConversationQueue />} />
          <Route path="/backoffice/conversations/:id" element={<ConversationDetail />} />
          <Route path="/backoffice/applications" element={<Navigate to="/backoffice/queue?tab=all" replace />} />
          {/* Queue Management */}
          <Route path="/backoffice/queue" element={<SmartQueue />} />
          <Route path="/backoffice/queue/config" element={<QueueConfigPage />} />
          <Route path="/backoffice/queue/analytics" element={<QueueAnalytics />} />
          <Route path="/backoffice/review/:id" element={<ApplicationReview />} />
          <Route path="/backoffice/reports" element={<Reports />} />
          <Route path="/backoffice/loans" element={<LoanBook />} />
          <Route path="/backoffice/collections" element={<Collections />} />
          <Route path="/backoffice/collections-dashboard" element={<CollectionsDashboard />} />
          <Route path="/backoffice/collection-sequences" element={<CollectionSequences />} />
          <Route path="/backoffice/collections/:id" element={<CollectionDetail />} />
          <Route path="/backoffice/new-application" element={<NewApplication />} />
          <Route path="/backoffice/products" element={<ProductManagement />} />
          <Route path="/backoffice/products/:id" element={<ProductDetail />} />
          <Route path="/backoffice/merchants" element={<MerchantManagement />} />
          <Route path="/backoffice/rules" element={<RulesManagement />} />
          <Route path="/backoffice/error-monitor" element={<ErrorMonitor />} />
          {/* User Management */}
          <Route path="/backoffice/users" element={<UserManagement />} />
          <Route path="/backoffice/users/new" element={<CreateUserForm />} />
          <Route path="/backoffice/users/roles" element={<RoleEditor />} />
          <Route path="/backoffice/users/roles/:roleId" element={<RoleDetailPage />} />
          <Route path="/backoffice/users/:userId" element={<UserDetail />} />
          <Route path="/backoffice/customers" element={<CustomerList />} />
          <Route path="/backoffice/customers/:id" element={<Customer360 />} />
          {/* Scorecards */}
          <Route path="/backoffice/scorecards" element={<ScorecardManagement />} />
          <Route path="/backoffice/scorecards/new" element={<CreateScorecardForm />} />
          <Route path="/backoffice/scorecards/:id" element={<ScorecardDetail />} />
          {/* Sector Analysis */}
          <Route path="/backoffice/sector-analysis" element={<SectorDashboard />} />
          <Route path="/backoffice/sector-analysis/policies" element={<SectorPolicies />} />
          <Route path="/backoffice/sector-analysis/:sectorName" element={<SectorDetail />} />
          {/* General Ledger */}
          <Route path="/backoffice/gl" element={<GLDashboard />} />
          <Route path="/backoffice/gl/accounts" element={<GLChartOfAccounts />} />
          <Route path="/backoffice/gl/entries" element={<GLJournalEntries />} />
          <Route path="/backoffice/gl/ledger" element={<GLAccountLedger />} />
          <Route path="/backoffice/gl/trial-balance" element={<GLTrialBalance />} />
          <Route path="/backoffice/gl/balance-sheet" element={<BalanceSheet />} />
          <Route path="/backoffice/gl/income-statement" element={<IncomeStatement />} />
          <Route path="/backoffice/gl/periods" element={<GLAccountingPeriods />} />
          <Route path="/backoffice/gl/mappings" element={<GLMappings />} />
          <Route path="/backoffice/gl/reports" element={<GLReports />} />
          <Route path="/backoffice/gl/report-builder" element={<ReportBuilder />} />
          <Route path="/backoffice/gl/anomalies" element={<AnomalyDashboard />} />
          <Route path="/backoffice/gl/chat" element={<GLChat />} />
          {/* Pre-Approval */}
          <Route path="/backoffice/pre-approvals" element={<PreApprovalDashboard />} />
          <Route path="/backoffice/pre-approvals/:ref" element={<PreApprovalDetail />} />
          {/* Audit */}
          <Route path="/backoffice/audit-trail" element={<AuditTrail />} />
        </Route>

        {/* Default redirect */}
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
