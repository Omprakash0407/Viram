"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, clearSession, getStoredSession, logout as apiLogout, type SessionUser } from "@/lib/api";

/**
 * Client-side session state. Tokens live in localStorage (kept out of React
 * state); this hook tracks *who* is signed in via /users/me.
 */
export function useSessionState() {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!getStoredSession()) {
        setLoading(false);
        return;
      }
      try {
        const me = await api<SessionUser>("/users/me");
        if (!cancelled) setUser(me);
      } catch {
        clearSession();
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const refresh = useCallback(async () => {
    try {
      const me = await api<SessionUser>("/users/me");
      setUser(me);
    } catch {
      setUser(null);
    }
  }, []);

  const signOut = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  return { user, loading, refresh, signOut };
}

type SessionContextValue = ReturnType<typeof useSessionState>;

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({
  children,
  value,
}: {
  children: React.ReactNode;
  value: SessionContextValue;
}) {
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}
