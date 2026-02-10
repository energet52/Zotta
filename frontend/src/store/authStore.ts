import { create } from 'zustand';
import { authApi } from '../api/endpoints';

interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  role: string;
  is_active: boolean;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; password: string; first_name: string; last_name: string; phone?: string }) => Promise<void>;
  logout: () => void;
  loadUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: !!localStorage.getItem('access_token'),
  isLoading: false,

  login: async (email, password) => {
    const response = await authApi.login({ email, password });
    const { access_token, refresh_token } = response.data;
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);
    // Also clear isLoading in case a stale loadUser() set it to true
    set({ isAuthenticated: true, isLoading: false });

    // Load user profile
    const userRes = await authApi.getMe();
    set({ user: userRes.data });
  },

  register: async (data) => {
    const response = await authApi.register(data);
    const { access_token, refresh_token } = response.data;
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);
    set({ isAuthenticated: true });

    const userRes = await authApi.getMe();
    set({ user: userRes.data });
  },

  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    set({ user: null, isAuthenticated: false });
  },

  loadUser: async () => {
    // Capture the token we're validating so we can detect if a concurrent
    // login replaced it before our request completes.
    const tokenAtStart = localStorage.getItem('access_token');
    set({ isLoading: true });
    try {
      const response = await authApi.getMe();
      set({ user: response.data, isAuthenticated: true, isLoading: false });
    } catch {
      // Only clear auth state if the token hasn't changed since we started.
      // A concurrent login() may have stored a fresh token — don't wipe it.
      const currentToken = localStorage.getItem('access_token');
      if (!currentToken || currentToken === tokenAtStart) {
        set({ user: null, isAuthenticated: false, isLoading: false });
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
      } else {
        // Token changed (fresh login happened) — just clear the loading flag.
        set({ isLoading: false });
      }
    }
  },
}));
