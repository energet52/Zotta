/**
 * usePermission hook — checks if the current user has a given permission.
 *
 * Uses the effective_permissions list from the /users/:id detail endpoint.
 * Falls back to legacy role-based checks for admin users.
 */

import { useState, useEffect, useCallback } from 'react';
import { useAuthStore } from '../store/authStore';
import { userApi } from '../api/endpoints';

let cachedPermissions: string[] | null = null;
let cacheUserId: number | null = null;
let fetchPromise: Promise<string[]> | null = null;

async function loadPermissions(userId: number): Promise<string[]> {
  if (cachedPermissions && cacheUserId === userId) {
    return cachedPermissions;
  }
  if (fetchPromise && cacheUserId === userId) {
    return fetchPromise;
  }
  cacheUserId = userId;
  fetchPromise = userApi
    .get(userId)
    .then((res) => {
      const perms: string[] = res.data.effective_permissions || [];
      cachedPermissions = perms;
      fetchPromise = null;
      return perms;
    })
    .catch(() => {
      fetchPromise = null;
      return [] as string[];
    });
  return fetchPromise;
}

export function clearPermissionCache() {
  cachedPermissions = null;
  cacheUserId = null;
  fetchPromise = null;
}

export function usePermission(...codes: string[]) {
  const { user } = useAuthStore();
  const [hasPermission, setHasPermission] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) {
      setHasPermission(false);
      setLoading(false);
      return;
    }

    // Admin bypass
    if (user.role === 'admin') {
      setHasPermission(true);
      setLoading(false);
      return;
    }

    let cancelled = false;
    loadPermissions(user.id).then((perms) => {
      if (!cancelled) {
        setHasPermission(codes.some((c) => perms.includes(c)));
        setLoading(false);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [user?.id, ...codes]);

  return { hasPermission, loading };
}

export function usePermissions() {
  const { user } = useAuthStore();
  const [permissions, setPermissions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) {
      setPermissions([]);
      setLoading(false);
      return;
    }

    let cancelled = false;
    loadPermissions(user.id).then((perms) => {
      if (!cancelled) {
        setPermissions(perms);
        setLoading(false);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [user?.id]);

  const hasPermission = useCallback(
    (...codes: string[]) => {
      if (user?.role === 'admin') return true;
      return codes.some((c) => permissions.includes(c));
    },
    [permissions, user?.role]
  );

  return { permissions, hasPermission, loading };
}
