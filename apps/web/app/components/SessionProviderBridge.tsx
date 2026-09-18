"use client";

import { useSessionState, SessionProvider } from "@/lib/session";

export function SessionProviderBridge({ children }: { children: React.ReactNode }) {
  const value = useSessionState();
  return <SessionProvider value={value}>{children}</SessionProvider>;
}
