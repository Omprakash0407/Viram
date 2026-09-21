"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Loader2, ShieldCheck, Users, MessageSquare, ScrollText } from "lucide-react";
import { useSession } from "@/lib/session";
import {
  adminApi,
  type AdminProviderRow,
  type CommunitySuggestionRow,
} from "@/lib/api";

type Tab = "providers" | "suggestions" | "audit";

const STATUS_CLS: Record<string, string> = {
  PENDING: "bg-amber-50 text-amber-800",
  APPROVED: "bg-emerald-50 text-emerald-800",
  REJECTED: "bg-red-50 text-red-800",
  SUSPENDED: "bg-red-50 text-red-800",
  VERIFIED: "bg-emerald-50 text-emerald-800",
};

function Pill({ status }: { status: string }) {
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${STATUS_CLS[status] ?? "bg-cream-dark text-ink"}`}>
      {status}
    </span>
  );
}

export default function AdminPage() {
  const { user, loading: sessionLoading } = useSession();
  const isAdmin = user?.account_role === "ADMIN";
  const [tab, setTab] = useState<Tab>("providers");
  const [providers, setProviders] = useState<AdminProviderRow[] | null>(null);
  const [suggestions, setSuggestions] = useState<CommunitySuggestionRow[] | null>(null);
  const [audit, setAudit] = useState<Array<Record<string, unknown>> | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(() => {
    if (!isAdmin) return;
    adminApi.providers().then(setProviders).catch(() => setProviders([]));
    adminApi.suggestions().then((r) => setSuggestions(r.items)).catch(() => setSuggestions([]));
    adminApi.auditLog().then((r) => setAudit(r.items)).catch(() => setAudit([]));
  }, [isAdmin]);

  useEffect(loadAll, [loadAll]);

  async function review(kind: "guide" | "business", id: string, decision: "APPROVED" | "REJECTED" | "SUSPENDED" | "REINSTATE") {
    setBusyId(id);
    setError(null);
    try {
      await adminApi.reviewProvider(kind, id, decision);
      setProviders((rows) => rows?.map((r) => (r.kind === kind.toUpperCase() && r.id === id ? { ...r, status: decision === "REINSTATE" ? "APPROVED" : decision } : r)) ?? rows);
      // The decision just appended an audit entry server-side — pull it in.
      adminApi.auditLog().then((r) => setAudit(r.items)).catch(() => undefined);
    } catch {
      setError("Decision failed — the row may have changed. Reloading.");
      loadAll();
    } finally {
      setBusyId(null);
    }
  }

  async function reviewSuggestion(id: string, decision: "APPROVED" | "REJECTED") {
    setBusyId(id);
    setError(null);
    try {
      await adminApi.reviewSuggestion(id, decision);
      setSuggestions((rows) => rows?.map((r) => (r.id === id ? { ...r, status: decision } : r)) ?? rows);
      // Keep the audit tab in sync with the freshly logged decision.
      adminApi.auditLog().then((r) => setAudit(r.items)).catch(() => undefined);
    } catch {
      setError("Decision failed. Reloading.");
      loadAll();
    } finally {
      setBusyId(null);
    }
  }

  if (sessionLoading) {
    return <main className="mx-auto max-w-5xl px-6 py-16 text-ink/50">Loading…</main>;
  }

  if (!user || !isAdmin) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <ShieldCheck className="h-10 w-10 text-forest" aria-hidden="true" />
        <h1 className="mt-4 font-display text-3xl font-semibold text-ink">Admin console</h1>
        <p className="mt-3 text-ink/70">
          This area is restricted to VIRĀM administrators (account role <code>ADMIN</code>).
          {user ? " Your account is not an admin account." : " Sign in with an admin account."}
        </p>
        {!user ? (
          <Link href="/login?next=%2Fadmin" className="mt-6 inline-block rounded-full bg-forest px-5 py-2.5 text-sm font-medium text-white hover:bg-forest-dark">
            Sign in
          </Link>
        ) : null}
      </main>
    );
  }

  const pendingProviders = providers?.filter((p) => p.status === "PENDING") ?? [];
  const otherProviders = providers?.filter((p) => p.status !== "PENDING") ?? [];

  const tabBtn = (t: Tab, label: string, Icon: typeof Users, count?: number) => (
    <button
      type="button"
      onClick={() => setTab(t)}
      aria-pressed={tab === t}
      className={`inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium ${
        tab === t ? "bg-forest text-white" : "bg-white text-ink shadow-sm hover:bg-cream-dark"
      }`}
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
      {label}
      {typeof count === "number" && count > 0 ? (
        <span className={`rounded-full px-2 py-0.5 text-xs ${tab === t ? "bg-white/20" : "bg-amber-100 text-amber-800"}`}>{count}</span>
      ) : null}
    </button>
  );

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <h1 className="font-display text-4xl font-semibold text-ink">Admin console</h1>
      <p className="mt-2 text-ink/60">Verification, moderation and audit — every decision is logged.</p>

      <div className="mt-8 flex flex-wrap gap-2">
        {tabBtn("providers", "Provider verification", Users, pendingProviders.length)}
        {tabBtn("suggestions", "Community suggestions", MessageSquare, suggestions?.filter((s) => s.status === "PENDING").length)}
        {tabBtn("audit", "Audit log", ScrollText)}
      </div>

      {error ? <p className="mt-4 text-sm text-red-800">{error}</p> : null}

      {tab === "providers" ? (
        providers === null ? (
          <p className="mt-8 text-ink/50">Loading…</p>
        ) : (
          <div className="mt-6 space-y-8">
            <section aria-labelledby="queue-h">
              <h2 id="queue-h" className="text-sm font-semibold uppercase tracking-wide text-ink/50">Pending review</h2>
              {pendingProviders.length === 0 ? (
                <p className="mt-3 rounded-2xl bg-white p-6 text-sm text-ink/60 shadow-sm">Queue is clear. 🎉</p>
              ) : (
                <ul className="mt-3 space-y-3">
                  {pendingProviders.map((p) => (
                    <li key={`${p.kind}-${p.id}`} className="rounded-2xl bg-white p-5 shadow-sm">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="font-medium text-ink">
                            {p.name} <span className="text-xs font-normal uppercase tracking-wide text-ink/50">· {p.kind} · {p.category ?? "—"}</span>
                          </p>
                          <p className="mt-0.5 text-sm text-ink/60">
                            by {p.owner_email ?? p.user_id}
                            {p.owner_identity_verified ? (
                              <span className="ml-2 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-800">identity verified</span>
                            ) : (
                              <span className="ml-2 rounded-full bg-cream-dark px-2 py-0.5 text-xs text-ink/60">identity not verified</span>
                            )}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <button type="button" disabled={busyId === p.id} onClick={() => void review(p.kind.toLowerCase() as "guide" | "business", p.id, "APPROVED")} className="rounded-full bg-forest px-4 py-2 text-xs font-semibold text-white hover:bg-forest-dark disabled:opacity-50">Approve</button>
                          <button type="button" disabled={busyId === p.id} onClick={() => void review(p.kind.toLowerCase() as "guide" | "business", p.id, "REJECTED")} className="rounded-full bg-white px-4 py-2 text-xs font-semibold text-red-800 ring-1 ring-red-200 hover:bg-red-50 disabled:opacity-50">Reject</button>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {otherProviders.length > 0 ? (
              <section aria-labelledby="decided-h">
                <h2 id="decided-h" className="text-sm font-semibold uppercase tracking-wide text-ink/50">Previously decided</h2>
                <ul className="mt-3 divide-y divide-cream-dark rounded-2xl bg-white shadow-sm">
                  {otherProviders.map((p) => (
                    <li key={`${p.kind}-${p.id}`} className="flex items-center justify-between gap-3 px-5 py-3">
                      <div>
                        <p className="text-sm font-medium text-ink">{p.name} <span className="text-xs text-ink/50">· {p.kind}</span></p>
                        {p.review_note ? <p className="text-xs text-ink/50">Note: {p.review_note}</p> : null}
                      </div>
                      <div className="flex items-center gap-2">
                        <Pill status={p.status} />
                        {p.status === "APPROVED" ? (
                          <button type="button" disabled={busyId === p.id} onClick={() => void review(p.kind.toLowerCase() as "guide" | "business", p.id, "SUSPENDED")} className="rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-ink ring-1 ring-cream-dark hover:bg-cream disabled:opacity-50">Suspend</button>
                        ) : p.status === "SUSPENDED" ? (
                          <button type="button" disabled={busyId === p.id} onClick={() => void review(p.kind.toLowerCase() as "guide" | "business", p.id, "REINSTATE")} className="rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-emerald-800 ring-1 ring-emerald-200 hover:bg-emerald-50 disabled:opacity-50">Reinstate</button>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </div>
        )
      ) : null}

      {tab === "suggestions" ? (
        suggestions === null ? (
          <p className="mt-8 text-ink/50">Loading…</p>
        ) : suggestions.length === 0 ? (
          <p className="mt-6 rounded-2xl bg-white p-6 text-sm text-ink/60 shadow-sm">No community submissions yet.</p>
        ) : (
          <ul className="mt-6 space-y-3">
            {suggestions.map((s) => (
              <li key={s.id} className="rounded-2xl bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="max-w-xl">
                    <p className="font-medium text-ink">{s.title}</p>
                    <p className="text-xs uppercase tracking-wide text-ink/50">{s.kind} · by {s.submitter_name}</p>
                    <p className="mt-2 text-sm text-ink/75">{s.body}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Pill status={s.status} />
                    {s.status === "PENDING" ? (
                      <>
                        <button type="button" disabled={busyId === s.id} onClick={() => void reviewSuggestion(s.id, "APPROVED")} className="rounded-full bg-forest px-4 py-2 text-xs font-semibold text-white hover:bg-forest-dark disabled:opacity-50">Approve</button>
                        <button type="button" disabled={busyId === s.id} onClick={() => void reviewSuggestion(s.id, "REJECTED")} className="rounded-full bg-white px-4 py-2 text-xs font-semibold text-red-800 ring-1 ring-red-200 hover:bg-red-50 disabled:opacity-50">Reject</button>
                      </>
                    ) : null}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )
      ) : null}

      {tab === "audit" ? (
        audit === null ? (
          <p className="mt-8 text-ink/50">Loading…</p>
        ) : audit.length === 0 ? (
          <p className="mt-6 rounded-2xl bg-white p-6 text-sm text-ink/60 shadow-sm">No administrative actions logged yet.</p>
        ) : (
          <ol className="mt-6 space-y-2">
            {audit.map((a, i) => (
              <li key={i} className="rounded-xl bg-white px-5 py-3 text-sm shadow-sm">
                <span className="font-mono text-xs text-forest">{String(a.action ?? "event")}</span>
                <span className="ml-2 text-ink/60">{String(a.target_type ?? "")} {String(a.target_id ?? "").slice(0, 8)}</span>
                <span className="ml-2 text-ink/70">{a.after ? JSON.stringify(a.after).slice(0, 120) : ""}</span>
                <span className="ml-2 text-xs text-ink/40">{a.created_at ? new Date(String(a.created_at)).toLocaleString("en-IN") : ""}</span>
              </li>
            ))}
          </ol>
        )
      ) : null}

      <p className="mt-10 flex items-center gap-2 text-xs text-ink/50">
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" style={{ display: busyId ? "inline" : "none" }} />
        {busyId ? "Applying…" : "Every decision stamps reviewer, timestamp and note, and appends an audit entry."}
      </p>
    </main>
  );
}
