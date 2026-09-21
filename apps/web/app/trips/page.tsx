"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  CalendarDays,
  ChevronDown,
  ChevronUp,
  Cloud,
  Loader2,
  MapPin,
  Phone,
  Users,
} from "lucide-react";
import Header from "@/app/components/Header";
import Footer from "@/app/components/Footer";
import LocationSharing from "./LocationSharing";
import SafeTravelSos from "./SafeTravelSos";

// Leaflet touches `window` at import time — load the map browser-only.
const CompanionsMap = dynamic(() => import("./CompanionsMap"), {
  ssr: false,
  loading: () => <p className="mt-2 text-sm text-ink/50">Loading live map…</p>,
});
import {
  commerceApi,
  companionsApi,
  tripsApi,
  type BookingRow,
  type CompanionRow,
  type InvitationRow,
  type SharedTripRow,
  type TripDetail,
  type TripListItem,
  type ItineraryDayRow,
} from "@/lib/api";
import { useSession } from "@/lib/session";

type Weather = {
  temperature_c: number;
  condition: string;
  retrieved_at: string;
  cached: boolean;
  city: { name: string };
};


const STATUS_STYLES: Record<string, string> = {
  PLANNING: "bg-amber-100 text-amber-800",
  BOOKED: "bg-blue-100 text-blue-800",
  CONFIRMED: "bg-emerald-100 text-emerald-800",
  COMPLETED: "bg-ink/10 text-ink/70",
  CANCELLED: "bg-red-100 text-red-700",
};

function fmt(d: string) {
  return new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export default function TripsPage() {
  const { user, loading: sessionLoading } = useSession();
  const [trips, setTrips] = useState<TripListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<TripDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [bookings, setBookings] = useState<BookingRow[]>([]);
  const [weather, setWeather] = useState<Weather | null>(null);
  const [invitations, setInvitations] = useState<InvitationRow[]>([]);
  const [shared, setShared] = useState<SharedTripRow[]>([]);
  const [companions, setCompanions] = useState<Record<string, CompanionRow[]>>({});
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteMsg, setInviteMsg] = useState<string | null>(null);

  const loadShared = useCallback(() => {
    if (!user) return;
    companionsApi.invitations().then((r) => setInvitations(r.items)).catch(() => setInvitations([]));
    companionsApi.shared().then((r) => setShared(r.items)).catch(() => setShared([]));
  }, [user]);

  useEffect(loadShared, [loadShared]);

  useEffect(() => {
    if (sessionLoading) return;
    if (!user) {
      setTrips([]);
      return;
    }
    tripsApi
      .list()
      .then((r) => setTrips(r.items))
      .catch(() => setError("Could not load your trips. Is the API running?"));
  }, [user, sessionLoading]);

  const openTrip = useCallback(async (t: TripListItem) => {
    if (openId === t.id) {
      setOpenId(null);
      setDetail(null);
      setBookings([]);
      setWeather(null);
      return;
    }
    setOpenId(t.id);
    setDetail(null);
    setBookings([]);
    setWeather(null);
    setDetailLoading(true);
    try {
      const d = await tripsApi.detail(t.id);
      setDetail(d);
      if (d.viewer_role === "HEAD") loadCompanions(t.id);
      // bookings + travel intelligence — failures are non-fatal, sections just stay hidden
      commerceApi
        .tripBookings(t.id)
        .then((b) =>
          setBookings([...b.hotel_bookings, ...b.guide_bookings]),
        )
        .catch(() => setBookings([]));
      try {
        const res = await fetch(
          `/api/v1/intelligence/weather?city_id=${d.city?.id ?? ""}`,
        );
        if (res.ok) setWeather(await res.json());
      } catch {}
    } catch {
      setError("Could not load that trip.");
    } finally {
      setDetailLoading(false);
    }
  }, [openId]);

  const itinerary = detail?.itinerary;

  function loadCompanions(tripId: string) {
    companionsApi
      .list(tripId)
      .then((r) => setCompanions((m) => ({ ...m, [tripId]: r.items.filter((c) => c.status !== "REMOVED") })))
      .catch(() => setCompanions((m) => ({ ...m, [tripId]: [] })));
  }

  async function invite(tripId: string) {
    setInviteMsg(null);
    const email = inviteEmail.trim();
    if (!email) return;
    try {
      const row = await companionsApi.invite(tripId, email);
      setInviteEmail("");
      setInviteMsg(`Invitation sent to ${row.companion_name}.`);
      loadCompanions(tripId);
    } catch (e) {
      setInviteMsg(e instanceof Error ? e.message : "Could not send the invitation.");
    }
  }

  async function removeCompanion(tripId: string, rowId: string) {
    try {
      await companionsApi.remove(tripId, rowId);
      loadCompanions(tripId);
    } catch {
      setInviteMsg("Could not remove that traveller.");
    }
  }

  async function respond(rowId: string, accept: boolean) {
    try {
      await (accept ? companionsApi.accept(rowId) : companionsApi.decline(rowId));
      loadShared();
    } catch {
      /* invitation already handled */
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-cream">
      <Header />
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10 sm:px-6">
        <header className="mb-8">
          <p className="text-xs font-semibold tracking-[0.2em] text-ink/50">TRIP DASHBOARD</p>
          <h1 className="mt-2 font-display text-4xl font-semibold text-ink">Your journeys</h1>
          <p className="mt-2 text-ink/70">
            Every plan, itinerary, booking and payment — in one place.
          </p>
        </header>

        {sessionLoading || (trips === null && !error) ? (
          <p className="flex items-center gap-2 py-16 text-ink/60">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" /> Loading…
          </p>
        ) : error ? (
          <p className="rounded-xl bg-red-50 p-4 text-sm text-red-700">{error}</p>
        ) : !user ? (
          <div className="rounded-2xl bg-white p-8 text-center shadow ring-1 ring-ink/5">
            <p className="text-ink/70">Sign in to see your trips.</p>
            <Link
              href="/login"
              className="mt-4 inline-block rounded-full bg-forest px-6 py-3 font-medium text-white hover:bg-forest-dark"
            >
              Sign in
            </Link>
          </div>
        ) : (
          <div className="space-y-6">
          {/* Travelling-together invitations */}
          {invitations.length > 0 && (
            <section aria-label="Trip invitations" className="rounded-2xl bg-forest p-5 text-cream shadow">
              <h2 className="font-display text-lg font-semibold">Travelling together</h2>
              <ul className="mt-3 space-y-2">
                {invitations.map((inv) => (
                  <li key={inv.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-forest-dark px-4 py-3">
                    <span className="text-sm">
                      <strong>{inv.invited_by_name}</strong> invited you to their trip
                      {inv.starts_on && inv.ends_on ? (
                        <> · {fmt(inv.starts_on)} → {fmt(inv.ends_on)}</>
                      ) : null}
                    </span>
                    <span className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => void respond(inv.id, true)}
                        className="rounded-full bg-cream px-4 py-1.5 text-sm font-semibold text-forest hover:bg-white"
                      >
                        Join trip
                      </button>
                      <button
                        type="button"
                        onClick={() => void respond(inv.id, false)}
                        className="rounded-full px-4 py-1.5 text-sm text-cream/80 underline underline-offset-4 hover:text-cream"
                      >
                        Decline
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Trips shared with me */}
          {shared.length > 0 && (
            <section aria-labelledby="shared-h">
              <h2 id="shared-h" className="font-display text-xl font-semibold text-ink">Shared with you</h2>
              <ul className="mt-3 space-y-3">
                {shared.map((s) => (
                  <li key={s.trip_id} className="rounded-2xl bg-white p-5 shadow ring-1 ring-ink/5">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-display text-lg font-semibold text-ink">
                          {fmt(s.starts_on)} → {fmt(s.ends_on)}
                        </p>
                        <p className="text-sm text-ink/60">
                          Planned by <strong>{s.head_name}</strong> · {s.party_size} travellers
                        </p>
                      </div>
                      <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${STATUS_STYLES[s.status] ?? "bg-ink/10 text-ink/60"}`}>
                        {s.status}
                      </span>
                    </div>
                    <SharedTripItinerary tripId={s.trip_id} />
                  </li>
                ))}
              </ul>
            </section>
          )}

          {trips?.length === 0 && invitations.length === 0 && shared.length === 0 ? (
            <div className="rounded-2xl bg-white p-8 text-center shadow ring-1 ring-ink/5">
              <p className="text-ink/70">No trips yet — your plans will appear here.</p>
              <Link
                href="/plan"
                className="mt-4 inline-block rounded-full bg-forest px-6 py-3 font-medium text-white hover:bg-forest-dark"
              >
                Plan your first trip
              </Link>
            </div>
          ) : null}

          <ul className="space-y-4">
            {(trips ?? []).map((t) => (
              <li key={t.id} className="overflow-hidden rounded-2xl bg-white shadow ring-1 ring-ink/5">
                <button
                  type="button"
                  onClick={() => void openTrip(t)}
                  aria-expanded={openId === t.id}
                  className="flex w-full items-center justify-between gap-4 p-5 text-left transition-colors hover:bg-cream/60"
                >
                  <div>
                    <div className="flex flex-wrap items-center gap-3">
                      <h2 className="font-display text-lg font-semibold text-ink">
                        {fmt(t.starts_on)} → {fmt(t.ends_on)}
                      </h2>
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${
                          STATUS_STYLES[t.status] ?? "bg-ink/10 text-ink/60"
                        }`}
                      >
                        {t.status}
                      </span>
                    </div>
                    <p className="mt-1 flex items-center gap-3 text-sm text-ink/60">
                      <span className="inline-flex items-center gap-1">
                        <CalendarDays className="h-3.5 w-3.5" aria-hidden="true" />
                        {(new Date(t.ends_on).getTime() - new Date(t.starts_on).getTime()) / 86400000 + 1} days
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <Users className="h-3.5 w-3.5" aria-hidden="true" />
                        {t.party_size} travellers
                      </span>
                    </p>
                  </div>
                  {openId === t.id ? (
                    <ChevronUp className="h-5 w-5 shrink-0 text-ink/40" aria-hidden="true" />
                  ) : (
                    <ChevronDown className="h-5 w-5 shrink-0 text-ink/40" aria-hidden="true" />
                  )}
                </button>

                {openId === t.id && (
                  <div className="border-t border-ink/10 bg-cream/40 p-5">
                    {detailLoading ? (
                      <p className="flex items-center gap-2 text-sm text-ink/60">
                        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Loading trip…
                      </p>
                    ) : detail ? (
                      <div className="space-y-6">
                        {/* Live location — opt-in sharing + companions map (beta) */}
                        <section aria-label="Live location">
                          <LocationSharing tripId={t.id} />
                          {detail.viewer_role === "HEAD" ? (
                            <CompanionsMap tripId={t.id} />
                          ) : null}
                        </section>

                        {/* Safe travel SOS — contacts + nearest hospital route */}
                        <section aria-label="Safe travel SOS">
                          <SafeTravelSos tripId={t.id} />
                        </section>

                        {/* Itinerary */}
                        <section>
                          <h3 className="font-display text-base font-semibold text-ink">Itinerary</h3>
                          {itinerary?.days?.length ? (
                            <div className="mt-3 space-y-3">
                              {itinerary.days.map((d) => (
                                <div key={d.day_number} className="rounded-xl bg-white p-4 ring-1 ring-ink/5">
                                  <p className="text-sm font-semibold text-ink">
                                    Day {d.day_number} · {fmt(d.date)}
                                  </p>
                                  <ul className="mt-2 space-y-1.5">
                                    {d.items.length === 0 && (
                                      <li className="text-xs text-ink/50">A lighter day.</li>
                                    )}
                                    {d.items.map((i) => (
                                      <li key={i.id} className="flex items-center gap-2 text-sm text-ink/80">
                                        <MapPin className="h-3.5 w-3.5 text-forest" aria-hidden="true" />
                                        {i.title}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="mt-2 text-sm text-ink/60">
                              No itinerary yet.{" "}
                              <Link href="/plan" className="underline">Generate one in the planner.</Link>
                            </p>
                          )}
                        </section>

                        {/* Travelling together — head manages companions */}
                        {detail.viewer_role === "HEAD" && (
                          <section aria-label="Travelling together">
                            <h3 className="font-display text-base font-semibold text-ink">
                              Travelling together
                            </h3>
                            <p className="mt-1 text-sm text-ink/60">
                              Invite the people travelling with you — they&apos;ll see this
                              itinerary after they accept. Your bookings stay private.
                            </p>
                            {(companions[t.id] ?? []).length > 0 && (
                              <ul className="mt-3 space-y-2">
                                {(companions[t.id] ?? []).map((c) => (
                                  <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-white p-3 ring-1 ring-ink/5">
                                    <span className="flex items-center gap-2 text-sm text-ink">
                                      {c.avatar_url ? (
                                        // eslint-disable-next-line @next/next/no-img-element -- data URL avatar
                                        <img src={c.avatar_url} alt="" className="h-7 w-7 rounded-full object-cover" />
                                      ) : (
                                        <span aria-hidden="true" className="flex h-7 w-7 items-center justify-center rounded-full bg-forest/10 text-xs font-semibold text-forest">
                                          {c.name.slice(0, 1).toUpperCase()}
                                        </span>
                                      )}
                                      {c.name}
                                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${c.status === "ACTIVE" ? "bg-emerald-50 text-emerald-800" : c.status === "INVITED" ? "bg-amber-50 text-amber-800" : "bg-ink/10 text-ink/60"}`}>
                                        {c.status}
                                      </span>
                                    </span>
                                    {c.status !== "REMOVED" && (
                                      <button
                                        type="button"
                                        onClick={() => void removeCompanion(t.id, c.id)}
                                        className="text-xs text-red-700 underline underline-offset-4 hover:text-red-800"
                                      >
                                        Remove
                                      </button>
                                    )}
                                  </li>
                                ))}
                              </ul>
                            )}
                            <div className="mt-3 flex flex-wrap gap-2">
                              <input
                                type="email"
                                value={inviteEmail}
                                onChange={(e) => setInviteEmail(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") void invite(t.id);
                                }}
                                placeholder="companion@email.com"
                                className="w-64 rounded-full bg-white px-4 py-2 text-sm text-ink ring-1 ring-ink/15 outline-none focus:ring-forest"
                              />
                              <button
                                type="button"
                                onClick={() => void invite(t.id)}
                                className="rounded-full bg-forest px-4 py-2 text-sm font-medium text-white hover:bg-forest-dark"
                              >
                                Invite
                              </button>
                            </div>
                            {inviteMsg ? <p className="mt-2 text-sm text-ink/70">{inviteMsg}</p> : null}
                          </section>
                        )}

                        {/* Bookings — hidden from companions (§24 stays intact) */}
                        {detail.viewer_role === "HEAD" && (
                        <section>
                          <h3 className="font-display text-base font-semibold text-ink">Bookings</h3>
                          {bookings.length === 0 ? (
                            <p className="mt-2 text-sm text-ink/60">No bookings on this trip yet.</p>
                          ) : (
                            <ul className="mt-3 space-y-2">
                              {bookings.map((b) => (
                                <li
                                  key={b.id}
                                  className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-white p-4 ring-1 ring-ink/5"
                                >
                                  <span className="text-sm text-ink">
                                    <strong>
                                      {b.hotel_name ? "Hotel" : "Guide"}
                                      {b.hotel_name ? ` · ${b.hotel_name}` : b.guide_name ? ` · ${b.guide_name}` : ""}
                                    </strong>{" "}
                                    · {b.reference_id}
                                  </span>
                                  <span className="flex items-center gap-2">
                                    <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${STATUS_STYLES[b.status] ?? "bg-ink/10 text-ink/60"}`}>
                                      {b.status}
                                    </span>
                                    <span className="text-sm text-ink/70">
                                      {b.currency} {(b.amount_paise / 100).toLocaleString("en-IN")}
                                    </span>
                                  </span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </section>
                        )}

                        {/* Weather */}
                        {weather && (
                          <section className="flex items-center gap-4 rounded-xl bg-white p-4 ring-1 ring-ink/5">
                            <Cloud className="h-8 w-8 text-forest" aria-hidden="true" />
                            <div>
                              <p className="text-sm font-semibold text-ink">
                                {weather.city.name}: {weather.temperature_c}°C, {weather.condition}
                              </p>
                              <p className="text-xs text-ink/50">
                                {weather.cached ? "Cached snapshot" : "Fresh from provider"} ·{" "}
                                {new Date(weather.retrieved_at).toLocaleString("en-IN")}
                              </p>
                            </div>
                          </section>
                        )}

                        {/* Emergency contacts now live in the Safe travel SOS panel above */}
                      </div>
                    ) : (
                      <p className="text-sm text-red-700">Could not load this trip.</p>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
          </div>
        )}
      </main>
      <Footer />
    </div>
  );
}

/** Read-only itinerary preview for a trip shared with this traveller. */
function SharedTripItinerary({ tripId }: { tripId: string }) {
  const [days, setDays] = useState<ItineraryDayRow[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    tripsApi
      .detail(tripId)
      .then((d) => {
        if (!cancelled) setDays(d.itinerary?.days ?? []);
      })
      .catch(() => {
        if (!cancelled) setDays([]);
      });
    return () => {
      cancelled = true;
    };
  }, [tripId]);

  if (days === null) {
    return <p className="mt-3 text-sm text-ink/50">Loading shared itinerary…</p>;
  }
  if (days.length === 0) {
    return <p className="mt-3 text-sm text-ink/60">No itinerary yet — {""}check back soon.</p>;
  }
  return (
    <details className="mt-3">
      <summary className="cursor-pointer text-sm font-semibold text-forest">
        View shared itinerary ({days.length} {days.length === 1 ? "day" : "days"})
      </summary>
      <ul className="mt-2 space-y-1.5">
        {days.map((d) => (
          <li key={d.day_number} className="text-sm text-ink/80">
            <strong>Day {d.day_number}</strong> · {fmt(d.date)}
            <ul className="ml-4 mt-1 list-disc space-y-0.5">
              {d.items.length === 0 ? (
                <li className="text-ink/50">A lighter day.</li>
              ) : (
                d.items.map((i) => <li key={i.id}>{i.title}</li>)
              )}
            </ul>
          </li>
        ))}
      </ul>
    </details>
  );
}
