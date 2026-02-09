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
import Profile from './apps/consumer/pages/Profile';

// Back-office pages
import UnderwriterDashboard from './apps/backoffice/pages/UnderwriterDashboard';
import Queue from './apps/backoffice/pages/Queue';
import ApplicationReview from './apps/backoffice/pages/ApplicationReview';
import Reports from './apps/backoffice/pages/Reports';
import LoanBook from './apps/backoffice/pages/LoanBook';
import Collections from './apps/backoffice/pages/Collections';
import CollectionDetail from './apps/backoffice/pages/CollectionDetail';
import NewApplication from './apps/backoffice/pages/NewApplication';

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
          <Route path="/applications" element={<Dashboard />} />
          <Route path="/applications/:id" element={<ApplicationStatus />} />
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
          <Route path="/backoffice/queue" element={<Queue />} />
          <Route path="/backoffice/review/:id" element={<ApplicationReview />} />
          <Route path="/backoffice/reports" element={<Reports />} />
          <Route path="/backoffice/loans" element={<LoanBook />} />
          <Route path="/backoffice/collections" element={<Collections />} />
          <Route path="/backoffice/collections/:id" element={<CollectionDetail />} />
          <Route path="/backoffice/new-application" element={<NewApplication />} />
        </Route>

        {/* Default redirect */}
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
