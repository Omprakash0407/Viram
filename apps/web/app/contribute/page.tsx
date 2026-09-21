"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Loader2, Landmark, Send } from "lucide-react";
import { geoApi, communityApi } from "@/lib/api";

const KINDS = [
  { value: "RITUAL", label: "Ritual or tradition" },
  { value: "FESTIVAL", label: "Festival or fair" },
  { value: "FOOD", label: "Local food" },
  { value: "CRAFT", label: "Craft or art form" },
  { value: "HISTORY", label: "Local history" },
  { value: "COMMUNITY", label: "Community or tribe" },
  { value: "LESSER_KNOWN_PLACE", label: "Lesser-known place" },
  { value: "EXPERIENCE", label: "Local experience" },
];

export default function ContributePage() {
  const [kind, setKind] = useState(KINDS[0].value);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [submitterName, setSubmitterName] = useState("");
  const [contact, setContact] = useState("");
  const [cityId, setCityId] = useState("");
  const [cities, setCities] = useState<Array<{ id: string; name: string }>>([]);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    geoApi
      .cities()
      .then((res) => setCities(res.items.map((c) => ({ id: c.id, name: c.name }))))
      .catch(() => setCities([]));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await communityApi.submit({
        kind,
        title: title.trim(),
        body: body.trim(),
        submitter_name: submitterName.trim(),
        contact: contact.trim() || null,
        city_id: cityId || null,
      });
      setDone(true);
    } catch {
      setError(
        body.trim().length < 20
          ? "Please describe it in at least 20 characters so the team can verify it."
          : "Could not submit right now. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-16 text-center">
        <Landmark className="mx-auto h-12 w-12 text-forest" aria-hidden="true" />
        <h1 className="mt-4 font-display text-3xl font-semibold text-ink">Thank you 🙏</h1>
        <p className="mt-3 text-ink/70">
          Your knowledge is now <strong>pending review</strong> by the VIRĀM team. Nothing is
          published automatically — a person verifies every submission before it appears on a
          destination page.
        </p>
        <button
          type="button"
          onClick={() => {
            setDone(false);
            setTitle("");
            setBody("");
          }}
          className="mt-8 rounded-full bg-forest px-5 py-2.5 text-sm font-medium text-white hover:bg-forest-dark"
        >
          Share something else
        </button>
      </main>
    );
  }

  const inputCls =
    "w-full rounded-xl border border-cream-dark bg-white px-4 py-2.5 text-sm text-ink outline-none focus:border-forest";

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <p className="text-sm font-semibold uppercase tracking-widest text-forest">Community knowledge</p>
      <h1 className="mt-2 font-display text-4xl font-semibold text-ink">Share what you know</h1>
      <p className="mt-3 text-ink/70">
        Are you local? Tell us about a ritual, a fair, a dish, a craft or a quiet place travellers
        would never find on their own. Verified submissions become part of VIRĀM&apos;s destination
        pages — credited to people, not scraped from lists.
      </p>

      <form onSubmit={submit} className="mt-8 space-y-4 rounded-2xl bg-white p-6 shadow-sm">
        <label className="block">
          <span className="text-sm font-medium text-ink">What is it? *</span>
          <select value={kind} onChange={(e) => setKind(e.target.value)} className={`mt-1 ${inputCls}`}>
            {KINDS.map((k) => (
              <option key={k.value} value={k.value}>{k.label}</option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">Title *</span>
          <input required minLength={5} maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} className={`mt-1 ${inputCls}`} placeholder="e.g. Chhera Panhara — the sweeping of the chariot" />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">Tell us about it *</span>
          <textarea required minLength={20} maxLength={6000} rows={6} value={body} onChange={(e) => setBody(e.target.value)} className={`mt-1 ${inputCls}`} placeholder="Describe it as you would to a curious traveller…" />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium text-ink">Your name *</span>
            <input required minLength={2} value={submitterName} onChange={(e) => setSubmitterName(e.target.value)} className={`mt-1 ${inputCls}`} placeholder="How should we credit you?" />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-ink">City / town</span>
            <select value={cityId} onChange={(e) => setCityId(e.target.value)} className={`mt-1 ${inputCls}`}>
              <option value="">Not city-specific</option>
              {cities.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </label>
        </div>
        <label className="block">
          <span className="text-sm font-medium text-ink">Contact (optional)</span>
          <input value={contact} onChange={(e) => setContact(e.target.value)} className={`mt-1 ${inputCls}`} placeholder="Email or phone — only for follow-up questions" />
        </label>

        {error ? <p className="text-sm text-red-800">{error}</p> : null}

        <button
          type="submit"
          disabled={busy}
          className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-forest px-5 py-3 text-sm font-medium text-white hover:bg-forest-dark disabled:opacity-60"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Send className="h-4 w-4" aria-hidden="true" />}
          Send for review
        </button>
        <p className="text-center text-xs text-ink/50">
          Submissions are never auto-published — a human verifies each one (design rule 7).
        </p>
      </form>
    </main>
  );
}
