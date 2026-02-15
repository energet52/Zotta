import { create } from 'zustand';
import { loanApi } from '../api/endpoints';

export type { Notification };

interface Notification {
  id: number;
  application_id: number;
  reference_number: string;
  content: string;
  author_name: string;
  created_at: string;
  read: boolean;
}

interface NotificationStore {
  notifications: Notification[];
  unreadCount: number;
  collectionMessageCount: number;
  loading: boolean;
  pollInterval: ReturnType<typeof setInterval> | null;
  fetch: () => Promise<void>;
  markAllRead: () => Promise<void>;
  markAppRead: (appId: number) => Promise<void>;
  startPolling: () => void;
  stopPolling: () => void;
}

export const useNotificationStore = create<NotificationStore>((set, get) => ({
  notifications: [],
  unreadCount: 0,
  collectionMessageCount: 0,
  loading: false,
  pollInterval: null,

  fetch: async () => {
    try {
      const res = await loanApi.getNotifications();
      const unread = res.data.unread_count || 0;

      // Also fetch collection messages count
      let colCount = 0;
      try {
        const colRes = await loanApi.getCollectionMessages();
        colCount = (colRes.data.messages || []).length;
      } catch { /* ignore */ }

      set({
        notifications: res.data.notifications || [],
        unreadCount: unread + (colCount > 0 ? 1 : 0),  // +1 indicator if collection msgs exist
        collectionMessageCount: colCount,
      });
    } catch {
      // silently ignore — user might not be logged in
    }
  },

  markAllRead: async () => {
    try {
      await loanApi.markAllNotificationsRead();
      set((state) => ({
        unreadCount: 0,
        notifications: state.notifications.map((n) => ({ ...n, read: true })),
      }));
    } catch { /* ignore */ }
  },

  markAppRead: async (appId: number) => {
    try {
      await loanApi.markCommentsRead(appId);
      set((state) => ({
        unreadCount: state.notifications.filter((n) => n.application_id === appId && !n.read).reduce((count) => count - 1, state.unreadCount),
        notifications: state.notifications.map((n) =>
          n.application_id === appId ? { ...n, read: true } : n
        ),
      }));
    } catch { /* ignore */ }
  },

  startPolling: () => {
    const { pollInterval, fetch } = get();
    if (pollInterval) return; // already polling
    fetch(); // immediate first fetch
    const interval = setInterval(fetch, 30_000); // poll every 30s
    set({ pollInterval: interval });
  },

  stopPolling: () => {
    const { pollInterval } = get();
    if (pollInterval) {
      clearInterval(pollInterval);
      set({ pollInterval: null });
    }
  },
}));
