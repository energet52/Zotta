import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../../store/authStore';
import Button from '../../../components/ui/Button';
import Input from '../../../components/ui/Input';
import Card from '../../../components/ui/Card';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      const user = useAuthStore.getState().user;
      if (user?.role === 'applicant') {
        navigate('/dashboard');
      } else {
        navigate('/backoffice');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="theme-consumer min-h-screen bg-[var(--color-bg)] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-[var(--color-primary)] rounded-2xl flex items-center justify-center mx-auto mb-4">
            <span className="text-3xl font-bold text-white">Z</span>
          </div>
          <h1 className="text-3xl font-bold text-[var(--color-text)]">Zotta</h1>
          <p className="text-[var(--color-text-muted)] mt-1">Consumer Lending Portal</p>
        </div>

        <Card padding="lg">
          <h2 className="text-xl font-semibold mb-6 text-[var(--color-text)]">Sign In</h2>
          {error && (
            <div className="mb-4 p-3 bg-red-500/20 text-red-400 rounded-lg text-sm border border-red-500/30">{error}</div>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@email.com"
              required
            />
            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
            />
            <Button type="submit" className="w-full" size="lg" isLoading={loading}>
              Sign In
            </Button>
          </form>
          <p className="text-center text-sm text-[var(--color-text-muted)] mt-6">
            Don't have an account?{' '}
            <Link to="/register" className="text-[var(--color-primary)] font-medium hover:underline">
              Register
            </Link>
          </p>
          <div className="mt-4 pt-4 border-t border-[var(--color-border)]">
            <p className="text-xs text-center text-[var(--color-text-muted)]">
              Staff member?{' '}
              <Link to="/login" className="text-[var(--color-primary)] hover:underline">
                Sign in with your staff credentials
              </Link>
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}
