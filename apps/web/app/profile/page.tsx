"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  BadgeCheck,
  ShieldCheck,
  Clock,
  XCircle,
  Loader2,
  Store,
  Compass,
  ChevronRight,
} from "lucide-react";
import { useSession } from "@/lib/session";
import {
  providersApi,
  usersApi,
  type BusinessProfileRow,
  type GuideProfileRow,
  type IdentityStatusRow,
} from "@/lib/api";

const STATUS_META: Record<string, { label: string; icon: typeof Clock; className: string }> = {
  PENDING: { label: "Pending review", icon: Clock, className: "text-amber-700 bg-amber-50" },
  APPROVED: { label: "Approved", icon: BadgeCheck, className: "text-emerald-800 bg-emerald-50" },
  REJECTED: { label: "Rejected", icon: XCircle, className: "text-red-800 bg-red-50" },
  SUSPENDED: { label: "Suspended", icon: XCircle, className: "text-red-800 bg-red-50" },
};

/**
 * Downscale an image file to a size×size square JPEG data URL in the browser.
 * Keeps avatars self-contained (~10–30 KB) so no object storage is needed.
 */
function downscaleToDataUrl(file: File, size: number): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext("2d");
        if (!ctx) throw new Error("canvas unavailable");
        // cover-crop: scale the larger dimension to fill the square
        const scale = Math.max(size / img.width, size / img.height);
        const w = img.width * scale;
        const h = img.height * scale;
        ctx.drawImage(img, (size - w) / 2, (size - h) / 2, w, h);
        URL.revokeObjectURL(url);
        resolve(canvas.toDataURL("image/jpeg", 0.85));
      } catch (err) {
        URL.revokeObjectURL(url);
        reject(err);
      }
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("not a readable image"));
    };
    img.src = url;
  });
}

function StatusPill({ status }: { status: string }) {
  const meta = STATUS_META[status] ?? STATUS_META.PENDING;
  const Icon = meta.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${meta.className}`}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {meta.label}
    </span>
  );
}

export default function ProfilePage() {
  const { user, loading: sessionLoading, refresh } = useSession();
  const [identity, setIdentity] = useState<IdentityStatusRow | null>(null);
  const [guide, setGuide] = useState<GuideProfileRow | null>(null);
  const [businesses, setBusinesses] = useState<BusinessProfileRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [avatar, setAvatar] = useState<string | null>(user?.avatar_url ?? null);
  const [avatarBusy, setAvatarBusy] = useState(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!user) return;
    providersApi.identityStatus().then(setIdentity).catch(() => setIdentity(null));
    providersApi.myGuide().then(setGuide).catch(() => setGuide(null));
    providersApi.myBusinesses().then(setBusinesses).catch(() => setBusinesses([]));
  }, [user]);

  async function startVerification() {
    setBusy(true);
    setError(null);
    try {
      const init = await providersApi.identityInit();
      // The consent_url is where the real DigiLocker flow would happen; the
      // demo verifier completes locally on the same "provider".
      await providersApi.identityComplete(init.verification.id);
      setIdentity(await providersApi.identityStatus());
    } catch {
      setError("Verification could not be started. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function onAvatarChosen(file: File) {
    setAvatarError(null);
    if (!/^image\/(png|jpeg|webp)$/.test(file.type)) {
      setAvatarError("Choose a PNG, JPG or WebP picture.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setAvatarError("That picture is too large (max 10 MB).");
      return;
    }
    setAvatarBusy(true);
    try {
      // Downscale client-side to a 128×128 square data URL — no upload infra
      // needed and the stored string stays small (~10–30 KB).
      const dataUrl = await downscaleToDataUrl(file, 128);
      await usersApi.updateProfile({ avatar_url: dataUrl });
      setAvatar(dataUrl);
      await refresh(); // header bubble picks it up immediately
    } catch {
      setAvatarError("Could not save the picture. Please try again.");
    } finally {
      setAvatarBusy(false);
    }
  }

  async function removeAvatar() {
    setAvatarError(null);
    setAvatarBusy(true);
    try {
      await usersApi.updateProfile({ avatar_url: null });
      setAvatar(null);
      await refresh();
    } catch {
      setAvatarError("Could not remove the picture. Please try again.");
    } finally {
      setAvatarBusy(false);
    }
  }

  if (sessionLoading) {
    return <main className="mx-auto max-w-4xl px-6 py-16 text-ink/50">Loading…</main>;
  }

  if (!user) {
    return (
      <main className="mx-auto max-w-4xl px-6 py-16">
        <h1 className="font-display text-3xl font-semibold text-ink">Your profile</h1>
        <p className="mt-3 text-ink/70">Sign in to manage your identity verification and provider profiles.</p>
        <Link
          href="/login?next=%2Fprofile"
          className="mt-6 inline-block rounded-full bg-forest px-5 py-2.5 text-sm font-medium text-white hover:bg-forest-dark"
        >
          Sign in
        </Link>
      </main>
    );
  }

  const identityMeta = identity?.latest?.status
    ? (STATUS_META[identity.latest.status === "VERIFIED" ? "APPROVED" : identity.latest.status] ??
      STATUS_META.PENDING)
    : null;

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <h1 className="font-display text-4xl font-semibold text-ink">
        {user.display_name || "Your profile"}
      </h1>
      <p className="mt-1 text-ink/60">{user.email}</p>

      {/* Profile picture */}
      <section className="mt-8 rounded-2xl bg-white p-6 shadow-sm" aria-labelledby="avatar-h">
        <h2 id="avatar-h" className="font-display text-xl font-semibold text-ink">Profile picture</h2>
        <div className="mt-4 flex flex-wrap items-center gap-5">
          {avatar ? (
            // eslint-disable-next-line @next/next/no-img-element -- self-contained data URL, not an optimized remote asset
            <img
              src={avatar}
              alt="Your profile picture"
              className="h-20 w-20 rounded-full object-cover ring-2 ring-forest/20"
            />
          ) : (
            <span
              aria-hidden="true"
              className="flex h-20 w-20 items-center justify-center rounded-full bg-forest/10 font-display text-2xl text-forest"
            >
              {(user.display_name || "V").slice(0, 1).toUpperCase()}
            </span>
          )}
          <div className="flex flex-col gap-2">
            <div className="flex gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void onAvatarChosen(f);
                  e.target.value = "";
                }}
              />
              <button
                type="button"
                disabled={avatarBusy}
                onClick={() => fileInputRef.current?.click()}
                className="rounded-full bg-forest px-4 py-2 text-sm font-medium text-white hover:bg-forest-dark disabled:opacity-50"
              >
                {avatarBusy ? "Saving…" : avatar ? "Change picture" : "Upload picture"}
              </button>
              {avatar ? (
                <button
                  type="button"
                  disabled={avatarBusy}
                  onClick={() => void removeAvatar()}
                  className="rounded-full bg-white px-4 py-2 text-sm font-medium text-ink ring-1 ring-ink/15 hover:bg-cream-dark disabled:opacity-50"
                >
                  Remove
                </button>
              ) : null}
            </div>
            {avatarError ? <p className="text-sm text-red-700">{avatarError}</p> : null}
          </div>
        </div>
      </section>

      {/* Identity verification */}
      <section className="mt-10 rounded-2xl bg-white p-6 shadow-sm" aria-labelledby="identity-h">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="identity-h" className="flex items-center gap-2 font-display text-xl font-semibold text-ink">
              <ShieldCheck className="h-5 w-5 text-forest" aria-hidden="true" />
              Identity verification
            </h2>
            <p className="mt-2 max-w-xl text-sm text-ink/70">
              Providers with a verified identity are trusted faster by travellers. VIRĀM confirms
              who you are through a DigiLocker-style check — your document numbers are never stored
              on our servers.
            </p>
          </div>
          {identity ? (
            <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${identityMeta?.className ?? "bg-cream-dark text-ink"}`}>
              {identity.identity_verified ? <BadgeCheck className="h-3.5 w-3.5" aria-hidden="true" /> : <Clock className="h-3.5 w-3.5" aria-hidden="true" />}
              {identity.identity_verified ? "Verified" : (identityMeta?.label ?? "Not started")}
            </span>
          ) : null}
        </div>

        {error ? <p className="mt-3 text-sm text-red-800">{error}</p> : null}

        {identity?.identity_verified ? (
          <p className="mt-4 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
            Your identity is verified{identity.latest?.verified_at ? ` (since ${new Date(identity.latest.verified_at).toLocaleDateString("en-IN")})` : ""}.
          </p>
        ) : (
          <button
            type="button"
            onClick={() => void startVerification()}
            disabled={busy}
            className="mt-4 inline-flex items-center gap-2 rounded-full bg-forest px-5 py-2.5 text-sm font-medium text-white hover:bg-forest-dark disabled:opacity-60"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <ShieldCheck className="h-4 w-4" aria-hidden="true" />}
            {busy ? "Verifying…" : "Verify your identity"}
          </button>
        )}
        {identity?.demo_note ? (
          <p className="mt-3 text-xs text-ink/50">{identity.demo_note}</p>
        ) : null}
      </section>

      {/* Guide profile */}
      <section className="mt-6 rounded-2xl bg-white p-6 shadow-sm" aria-labelledby="guide-h">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 id="guide-h" className="flex items-center gap-2 font-display text-xl font-semibold text-ink">
              <Compass className="h-5 w-5 text-forest" aria-hidden="true" />
              Guide profile
            </h2>
            {guide ? (
              <>
                <p className="mt-2 font-medium text-ink">{guide.public_name}</p>
                {guide.day_rate_paise ? (
                  <p className="text-sm text-ink/60">₹{guide.day_rate_paise / 100} / day</p>
                ) : null}
              </>
            ) : (
              <p className="mt-2 text-sm text-ink/70">
                Share your knowledge of your home region with travellers.
              </p>
            )}
          </div>
          <div className="flex shrink-0 flex-col items-end gap-2">
            {guide ? <StatusPill status={guide.status} /> : null}
            <Link
              href="/join?type=guide"
              className="inline-flex items-center gap-1 text-sm font-medium text-forest hover:underline"
            >
              {guide ? "Edit" : "Become a guide"}
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>

      {/* Business profiles */}
      <section className="mt-6 rounded-2xl bg-white p-6 shadow-sm" aria-labelledby="biz-h">
        <div className="flex items-center justify-between gap-4">
          <h2 id="biz-h" className="flex items-center gap-2 font-display text-xl font-semibold text-ink">
            <Store className="h-5 w-5 text-forest" aria-hidden="true" />
            Business profiles
          </h2>
          <Link
            href="/join?type=business"
            className="inline-flex items-center gap-1 text-sm font-medium text-forest hover:underline"
          >
            Add a business
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </div>
        {businesses.length === 0 ? (
          <p className="mt-3 text-sm text-ink/70">
            List your café, craft, homestay or experience to reach travellers on VIRĀM.
          </p>
        ) : (
          <ul className="mt-4 divide-y divide-cream-dark">
            {businesses.map((b) => (
              <li key={b.id} className="flex items-center justify-between gap-4 py-3">
                <div>
                  <p className="font-medium text-ink">{b.name}</p>
                  <p className="text-xs uppercase tracking-wide text-ink/50">{b.category}</p>
                </div>
                <StatusPill status={b.status} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
