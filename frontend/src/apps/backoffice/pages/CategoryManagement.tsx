import { Navigate } from 'react-router-dom';

/**
 * Categories are now managed per merchant.
 * This redirect ensures any legacy links land in the right place.
 */
export default function CategoryManagement() {
  return <Navigate to="/backoffice/merchants" replace />;
}
