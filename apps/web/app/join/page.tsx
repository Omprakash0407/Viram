"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Loader2, ShieldCheck, Compass, Store } from "lucide-react";
import { useSession } from "@/lib/session";
import {
  geoApi,
  providersApi,
  type BusinessProfileRow,
  type GuideProfileRow,
} from "@/lib/api";

const CATEGORIES = [
  "CAFE",
  "RESTAURANT",
  "ARTISAN",
  "HANDICRAFT",
  "HOMESTAY",
  "FOOD",
  "TOUR",
  "EXPERIENCE",
  "OTHER",
] as const;

type Kind = "guide" | "business";

export default function JoinPage() {
  // useSearchParams needs a Suspense boundary during static prerender.
  return (
    <Suspense fallback={<main className="mx-auto max-w-2xl px-6 py-16 text-ink/50">Loading…</main>}>
      <JoinForm />
    </Suspense>
  );
}

function JoinForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { user, loading: sessionLoading } = useSession();

  const kind: Kind = params.get("type") === "business" ? "business" : "guide";
  const [cities, setCities] = useState<Array<{ id: string; name: string }>>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<GuideProfileRow | BusinessProfileRow | null>(null);

  // guide fields
  const [publicName, setPublicName] = useState("");
  const [bio, setBio] = useState("");
  const [languages, setLanguages] = useState("");
  const [expertise, setExpertise] = useState("");
  const [cityId, setCityId] = useState("");
  const [rate, setRate] = useState("");

  // business fields
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<string>("CAFE");
  const [services, setServices] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState("");

  useEffect(() => {
    geoApi
      .cities()
      .then((res) => setCities(res.items.map((c) => ({ id: c.id, name: c.name }))))
      .catch(() => setCities([]));
  }, []);

  // Pre-fill guide form from an existing profile
  useEffect(() => {
    if (kind !== "guide" || !user) return;
    providersApi
      .myGuide()
      .then((g) => {
        if (!g) return;
        setPublicName(g.public_name);
        setBio(g.bio ?? "");
        setLanguages(g.languages.join(", "));
        setExpertise(g.expertise.join(", "));
        setCityId(g.city_id ?? "");
        setRate(g.day_rate_paise ? String(g.day_rate_paise / 100) : "");
      })
      .catch(() => undefined);
  }, [kind, user]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (kind === "guide") {
        const saved = await providersApi.saveGuide({
          public_name: publicName.trim(),
          bio: bio.trim() || null,
          languages: languages.split(",").map((s) => s.trim()).filter(Boolean),
          expertise: expertise.split(",").map((s) => s.trim()).filter(Boolean),
          areas_served: cityId ? [cities.find((c) => c.id === cityId)?.name ?? ""] : [],
          city_id: cityId || null,
          day_rate_paise: rate ? Math.round(parseFloat(rate) * 100) : null,
        });
        setCreated(saved);
      } else {
        const createdBiz = await providersApi.createBusiness({
          name: name.trim(),
          description: description.trim() || null,
          category,
          city_id: cityId,
          services: services.split(",").map((s) => s.trim()).filter(Boolean),
          public_phone: phone.trim() || null,
          public_email: email.trim() || null,
          public_address: address.trim() || null,
        });
        setCreated(createdBiz);
      }
    } catch (err) {
      setError(
        err instanceof Error && err.message.includes("409")
          ? "You already have a guide profile — edit it from your profile page."
          : "Could not save your profile. Check the fields and try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (sessionLoading) {
    return <main className="mx-auto max-w-2xl px-6 py-16 text-ink/50">Loading…</main>;
  }

  if (!user) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-16">
        <h1 className="font-display text-3xl font-semibold text-ink">
          {kind === "guide" ? "Become a VIRĀM guide" : "List your business"}
        </h1>
        <p className="mt-3 text-ink/70">
          Sign in first — your provider profile attaches to your account.
        </p>
        <Link
          href={`/login?next=${encodeURIComponent(`/join?type=${kind}`)}`}
          className="mt-6 inline-block rounded-full bg-forest px-5 py-2.5 text-sm font-medium text-white hover:bg-forest-dark"
        >
          Sign in
        </Link>
      </main>
    );
  }

  if (created) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-16 text-center">
        <ShieldCheck className="mx-auto h-12 w-12 text-forest" aria-hidden="true" />
        <h1 className="mt-4 font-display text-3xl font-semibold text-ink">
          {kind === "guide" ? "Guide profile submitted" : "Business submitted"}
        </h1>
        <p className="mt-3 text-ink/70">
          It&apos;s now <strong>pending verification</strong> by the VIRĀM team. You&apos;ll see the
          status on your profile — once approved, travellers can find you.
        </p>
        <div className="mt-8 flex justify-center gap-3">
          <Link
            href="/profile"
            className="rounded-full bg-forest px-5 py-2.5 text-sm font-medium text-white hover:bg-forest-dark"
          >
            Go to my profile
          </Link>
          <Link
            href="/partners"
            className="rounded-full bg-white px-5 py-2.5 text-sm font-medium text-ink shadow-sm hover:bg-cream-dark"
          >
            Browse partners
          </Link>
        </div>
      </main>
    );
  }

  const inputCls =
    "w-full rounded-xl border border-cream-dark bg-white px-4 py-2.5 text-sm text-ink outline-none focus:border-forest";

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <div className="mb-8 flex gap-2" role="tablist" aria-label="Provider type">
        <Link
          href="/join?type=guide"
          role="tab"
          aria-selected={kind === "guide"}
          className={`inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium ${
            kind === "guide" ? "bg-forest text-white" : "bg-white text-ink shadow-sm hover:bg-cream-dark"
          }`}
        >
          <Compass className="h-4 w-4" aria-hidden="true" />
          Guide
        </Link>
        <Link
          href="/join?type=business"
          role="tab"
          aria-selected={kind === "business"}
          className={`inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium ${
            kind === "business" ? "bg-forest text-white" : "bg-white text-ink shadow-sm hover:bg-cream-dark"
          }`}
        >
          <Store className="h-4 w-4" aria-hidden="true" />
          Business
        </Link>
      </div>

      <h1 className="font-display text-3xl font-semibold text-ink">
        {kind === "guide" ? "Become a VIRĀM guide" : "List your business"}
      </h1>
      <p className="mt-2 text-sm text-ink/70">
        {kind === "guide"
          ? "Tell travellers who you are, what you know, and how they can walk with you."
          : "Put your café, craft or experience in front of travellers planning their trip."}{" "}
        Every submission is reviewed by the VIRĀM team before it goes live.
      </p>

      <form onSubmit={submit} className="mt-8 space-y-4 rounded-2xl bg-white p-6 shadow-sm">
        {kind === "guide" ? (
          <>
            <label className="block">
              <span className="text-sm font-medium text-ink">Public name *</span>
              <input required minLength={2} value={publicName} onChange={(e) => setPublicName(e.target.value)} className={`mt-1 ${inputCls}`} placeholder="e.g. Sushil — Puri heritage walks" />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-ink">Bio</span>
              <textarea rows={4} value={bio} onChange={(e) => setBio(e.target.value)} className={`mt-1 ${inputCls}`} placeholder="Your story, your style of guiding…" />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="text-sm font-medium text-ink">Languages (comma-separated)</span>
                <input value={languages} onChange={(e) => setLanguages(e.target.value)} className={`mt-1 ${inputCls}`} placeholder="Odia, Hindi, English" />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-ink">Expertise</span>
                <input value={expertise} onChange={(e) => setExpertise(e.target.value)} className={`mt-1 ${inputCls}`} placeholder="Temples, Birdwatching" />
              </label>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="text-sm font-medium text-ink">Home city</span>
                <select value={cityId} onChange={(e) => setCityId(e.target.value)} className={`mt-1 ${inputCls}`}>
                  <option value="">Select a city</option>
                  {cities.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-sm font-medium text-ink">Day rate (₹)</span>
                <input type="number" min={1} value={rate} onChange={(e) => setRate(e.target.value)} className={`mt-1 ${inputCls}`} placeholder="1500" />
              </label>
            </div>
          </>
        ) : (
          <>
            <label className="block">
              <span className="text-sm font-medium text-ink">Business name *</span>
              <input required minLength={2} value={name} onChange={(e) => setName(e.target.value)} className={`mt-1 ${inputCls}`} placeholder="e.g. Raghurajpur Craft House" />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-ink">Description</span>
              <textarea rows={4} value={description} onChange={(e) => setDescription(e.target.value)} className={`mt-1 ${inputCls}`} placeholder="What you make, serve or host…" />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="text-sm font-medium text-ink">Category *</span>
                <select required value={category} onChange={(e) => setCategory(e.target.value)} className={`mt-1 ${inputCls}`}>
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>{c.charAt(0) + c.slice(1).toLowerCase()}</option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-sm font-medium text-ink">City *</span>
                <select required value={cityId} onChange={(e) => setCityId(e.target.value)} className={`mt-1 ${inputCls}`}>
                  <option value="">Select a city</option>
                  {cities.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </label>
            </div>
            <label className="block">
              <span className="text-sm font-medium text-ink">Services (comma-separated)</span>
              <input value={services} onChange={(e) => setServices(e.target.value)} className={`mt-1 ${inputCls}`} placeholder="Pattachitra workshops, Palm-leaf engravings" />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="text-sm font-medium text-ink">Public phone</span>
                <input value={phone} onChange={(e) => setPhone(e.target.value)} className={`mt-1 ${inputCls}`} placeholder="+91 …" />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-ink">Public email</span>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={`mt-1 ${inputCls}`} placeholder="you@example.com" />
              </label>
            </div>
            <label className="block">
              <span className="text-sm font-medium text-ink">Public address</span>
              <input value={address} onChange={(e) => setAddress(e.target.value)} className={`mt-1 ${inputCls}`} placeholder="Street, town" />
            </label>
          </>
        )}

        {error ? <p className="text-sm text-red-800">{error}</p> : null}

        <button
          type="submit"
          disabled={busy}
          className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-forest px-5 py-3 text-sm font-medium text-white hover:bg-forest-dark disabled:opacity-60"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
          {kind === "guide" ? "Submit guide profile" : "Submit business"}
        </button>
        <p className="text-center text-xs text-ink/50">
          Submitting adds this to the admin verification queue as <strong>PENDING</strong>. Nothing
          goes public without approval.
        </p>
      </form>
    </main>
  );
}
