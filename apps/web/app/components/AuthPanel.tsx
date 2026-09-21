"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login, register, AuthRequiredError, HttpError } from "@/lib/api";
import { useSession } from "@/lib/session";

type Mode = "login" | "register";

/**
 * Sign-in gate for traveller flows. Next.js middleware-free approach: pages
 * that need auth render <AuthGate> around their content; unauthenticated
 * visitors get this screen instead.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { user, loading } = useSession();
  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-sm text-ink/60">
        Checking your session…
      </div>
    );
  }
  if (!user) return <AuthPanel purpose="Use your VIRĀM account to plan and manage trips." />;
  return <>{children}</>;
}

export function AuthPanel({ purpose }: { purpose: string }) {
  const router = useRouter();
  const { refresh } = useSession();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [justAuthed, setJustAuthed] = useState(false);

  useEffect(() => {
    if (justAuthed) {
      void refresh();
      // Honour ?next= for flows that hand off to sign-in (e.g. the chatbot
      // carrying an unsent trip draft). Same-app relative paths only.
      const next = new URLSearchParams(window.location.search).get("next");
      router.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : "/plan");
    }
  }, [justAuthed, refresh, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "register") {
        await register(email.trim(), password, displayName.trim() || email.split("@")[0]);
      } else {
        await login(email.trim(), password);
      }
      setJustAuthed(true);
    } catch (err) {
      if (err instanceof HttpError) setError(err.apiError.message);
      else if (err instanceof AuthRequiredError) setError(err.message);
      else setError("Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-md rounded-2xl bg-white/70 p-8 shadow-sm ring-1 ring-ink/10">
      <h1 className="font-display text-3xl font-semibold text-ink">
        {mode === "login" ? "Welcome back" : "Create your account"}
      </h1>
      <p className="mt-2 text-sm text-ink/70">{purpose}</p>

      {process.env.NEXT_PUBLIC_STATIC_DEMO === "1" && (
        <p role="note" className="mt-4 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800 ring-1 ring-amber-200">
          This is a static preview — accounts and bookings need the live
          VIRĀM backend. Browse the Explore pages to see the full experience.
        </p>
      )}

      <form onSubmit={submit} className="mt-6 space-y-4">
        {mode === "register" && (
          <div>
            <label htmlFor="displayName" className="mb-1 block text-sm font-medium text-ink/80">
              Display name
            </label>
            <input
              id="displayName"
              type="text"
              autoComplete="name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full rounded-lg border border-ink/15 bg-white px-3 py-2.5 text-sm outline-none focus:border-forest"
              placeholder="Asha"
            />
          </div>
        )}
        <div>
          <label htmlFor="email" className="mb-1 block text-sm font-medium text-ink/80">
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border border-ink/15 bg-white px-3 py-2.5 text-sm outline-none focus:border-forest"
            placeholder="you@example.com"
          />
        </div>
        <div>
          <label htmlFor="password" className="mb-1 block text-sm font-medium text-ink/80">
            Password
          </label>
          <input
            id="password"
            type="password"
            required
            minLength={mode === "register" ? 8 : 1}
            autoComplete={mode === "register" ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-ink/15 bg-white px-3 py-2.5 text-sm outline-none focus:border-forest"
            placeholder={mode === "register" ? "At least 8 characters" : "Your password"}
          />
        </div>

        {error && (
          <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-forest px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-forest-dark disabled:opacity-60"
        >
          {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
        </button>
      </form>

      <p className="mt-5 text-center text-sm text-ink/70">
        {mode === "login" ? (
          <>
            New to VIRĀM?{" "}
            <button type="button" className="font-semibold text-forest underline underline-offset-4" onClick={() => setMode("register")}>
              Create an account
            </button>
          </>
        ) : (
          <>
            Already have an account?{" "}
            <button type="button" className="font-semibold text-forest underline underline-offset-4" onClick={() => setMode("login")}>
              Sign in
            </button>
          </>
        )}
      </p>
      <p className="mt-4 text-center text-xs text-ink/50">
        <Link href="/" className="underline underline-offset-4 hover:text-ink">
          Back to home
        </Link>
      </p>
    </div>
  );
}
