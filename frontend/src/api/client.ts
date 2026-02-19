import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Token refresh machinery ──────────────────────────────────
let isRefreshing = false;
let pendingQueue: {
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
}[] = [];

function processPendingQueue(error: unknown, token: string | null) {
  for (const p of pendingQueue) {
    if (token) p.resolve(token);
    else p.reject(error);
  }
  pendingQueue = [];
}

async function tryRefreshToken(): Promise<string> {
  const refreshToken = localStorage.getItem('refresh_token');
  if (!refreshToken) throw new Error('No refresh token');

  const res = await axios.post(`${API_URL}/api/auth/refresh`, {
    refresh_token: refreshToken,
  });

  const { access_token, refresh_token: newRefresh } = res.data;
  localStorage.setItem('access_token', access_token);
  localStorage.setItem('refresh_token', newRefresh);
  return access_token;
}

// Handle 401 responses: attempt silent refresh before giving up.
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as Record<string, unknown> & {
      _retry?: boolean;
      url?: string;
      headers: Record<string, string>;
    };
    if (!originalRequest) return Promise.reject(error);

    const url = originalRequest.url || '';
    const isAuthEndpoint =
      url.includes('/auth/login') ||
      url.includes('/auth/register') ||
      url.includes('/auth/refresh');

    if (error.response?.status !== 401 || isAuthEndpoint || originalRequest._retry) {
      return Promise.reject(error);
    }

    // If a refresh is already in flight, queue this request
    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        pendingQueue.push({ resolve, reject });
      }).then((token) => {
        originalRequest.headers.Authorization = `Bearer ${token}`;
        return api(originalRequest);
      });
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      const newToken = await tryRefreshToken();
      processPendingQueue(null, newToken);
      originalRequest.headers.Authorization = `Bearer ${newToken}`;
      return api(originalRequest);
    } catch (refreshError) {
      processPendingQueue(refreshError, null);

      // Refresh failed — clear auth and redirect to login
      const currentToken = localStorage.getItem('access_token');
      const requestToken = originalRequest.headers?.Authorization?.toString().replace('Bearer ', '');
      if (!currentToken || currentToken === requestToken) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
      }
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);

export default api;
