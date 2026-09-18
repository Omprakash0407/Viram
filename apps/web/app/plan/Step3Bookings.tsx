"use client";

import { useCallback, useEffect, useState } from "react";
import { BedDouble, CheckCircle2, ShieldCheck, Ticket, UserRound } from "lucide-react";
import {
  commerceApi,
  formatPaise,
  HttpError,
  type BookingRow,
  type GuideRow,
  type HotelRow,
  type RoomTypeRow,
  type TripDetail,
} from "@/lib/api";
import { PrimaryButton, SecondaryButton } from "./wizard-ui";

type Pending =
  | { kind: "hotel"; hotel: HotelRow; room: RoomTypeRow }
  | { kind: "guide"; guide: GuideRow };

/**
 * Step 3 — Bookings. Real Phase-5 flow against /hotels, /guides,
 * /hotel-bookings, /guide-bookings and /payments.
 *
 * Honesty rules (non-negotiable 12): hotel rooms are request-based — the UI
 * never claims guaranteed availability; flights/tickets (not in the MVP
 * schema) stay explicitly "coming later"; the payment gateway in dev is the
 * clearly-labelled MOCK gateway with a "Simulate payment" control.
 */
export function Step3Bookings({
  trip,
  onBack,
}: {
  trip: TripDetail;
  onBack: () => void;
}) {
  const city = trip.city?.name ?? "your destination";
  const days = trip.itinerary?.days ?? [];

  const [hotels, setHotels] = useState<HotelRow[]>([]);
  const [guides, setGuides] = useState<GuideRow[]>([]);
  const [existing, setExisting] = useState<{ hotel_bookings: BookingRow[]; guide_bookings: BookingRow[] } | null>(null);
  const [roomsFor, setRoomsFor] = useState<string | null>(null);
  const [rooms, setRooms] = useState<RoomTypeRow[]>([]);
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reloadBookings = useCallback(async () => {
    try {
      setExisting(await commerceApi.tripBookings(trip.id));
    } catch {
      setExisting(null);
    }
  }, [trip.id]);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        if (!trip.city) return;
        const [h, g] = await Promise.all([
          commerceApi.hotels(trip.city.id),
          commerceApi.guides(trip.city.id),
        ]);
        if (live) {
          setHotels(h.items);
          setGuides(g.items);
        }
      } catch (e) {
        if (live) setError(e instanceof HttpError ? e.message : "Could not load providers.");
      }
    })();
    void reloadBookings();
    return () => {
      live = false;
    };
  }, [trip.city, reloadBookings]);

  async function openRooms(hotelId: string) {
    setRoomsFor(hotelId);
    setRooms([]);
    try {
      const r = await commerceApi.rooms(hotelId);
      setRooms(r.items);
    } catch (e) {
      setError(e instanceof HttpError ? e.message : "Could not load rooms.");
    }
  }

  async function requestHotelBooking() {
    if (!pending || pending.kind !== "hotel" || !trip.city) return;
    setBusy(true);
    setError(null);
    try {
      // MVP request-based booking: check-in = trip start, check-out = day after end.
      await commerceApi.createHotelBooking({
        hotel_id: pending.hotel.id,
        room_type_id: pending.room.id,
        check_in_date: trip.starts_on,
        check_out_date: trip.ends_on === trip.starts_on ? nextDay(trip.ends_on) : dayAfter(trip.ends_on),
        rooms_count: 1,
        trip_id: trip.id,
      });
      setPending(null);
      setRoomsFor(null);
      await reloadBookings();
    } catch (e) {
      setError(e instanceof HttpError ? e.message : "Booking request failed.");
    } finally {
      setBusy(false);
    }
  }

  async function requestGuideBooking(guide: GuideRow) {
    setBusy(true);
    setError(null);
    try {
      // single-day guide service on the trip's first day
      await commerceApi.createGuideBooking({
        guide_profile_id: guide.id,
        service_start_date: trip.starts_on,
        service_end_date: trip.starts_on,
        trip_id: trip.id,
      });
      setPending(null);
      await reloadBookings();
    } catch (e) {
      setError(e instanceof HttpError ? e.message : "Guide booking failed.");
    } finally {
      setBusy(false);
    }
  }

  async function payAndConfirm(booking: BookingRow, kind: "hotel" | "guide") {
    setBusy(true);
    setError(null);
    try {
      const payment = await commerceApi.createPayment(
        kind === "hotel"
          ? { hotel_booking_id: booking.id, idempotency_key: `web-${booking.id}` }
          : { guide_booking_id: booking.id, idempotency_key: `web-${booking.id}` },
      );
      if (payment.mock_checkout) {
        await commerceApi.mockConfirm(payment.id);
      }
      await reloadBookings();
    } catch (e) {
      setError(e instanceof HttpError ? e.message : "Payment failed.");
    } finally {
      setBusy(false);
    }
  }

  async function cancel(booking: BookingRow, kind: "hotel" | "guide") {
    setBusy(true);
    setError(null);
    try {
      if (kind === "hotel") await commerceApi.cancelHotelBooking(booking.id);
      else await commerceApi.cancelGuideBooking(booking.id);
      await reloadBookings();
    } catch (e) {
      setError(e instanceof HttpError ? e.message : "Cancellation failed.");
    } finally {
      setBusy(false);
    }
  }

  const hotelBookings = existing?.hotel_bookings ?? [];
  const guideBookings = existing?.guide_bookings ?? [];

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold tracking-[0.3em] text-ink/50">STEP 3 · BOOKINGS</p>
        <h1 className="mt-1 font-display text-4xl font-semibold text-ink">
          Bookings for your {days.length}-day {city} trip
        </h1>
        <p className="mt-1 text-sm text-ink/60">
          Request stays and verified local guides, then pay securely. Rooms are
          request-based — the platform does not pretend live availability exists.
        </p>
      </div>

      {error && (
        <p role="alert" className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}

      {/* existing bookings */}
      {(hotelBookings.length > 0 || guideBookings.length > 0) && (
        <div className="space-y-3">
          <h2 className="font-display text-xl font-semibold text-ink">Your bookings</h2>
          {[
            ...hotelBookings.map((b) => ({ row: b, kind: "hotel" as const })),
            ...guideBookings.map((b) => ({ row: b, kind: "guide" as const })),
          ].map(({ row, kind }) => (
            <div key={row.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-white/70 p-4 ring-1 ring-ink/10">
              <div>
                <p className="font-semibold text-ink">
                  {row.hotel_name ?? row.guide_name}{" "}
                  <span className="ml-1 text-xs font-normal text-ink/50">{row.reference_id}</span>
                </p>
                <p className="text-sm text-ink/60">
                  {kind === "hotel"
                    ? `${row.check_in_date} → ${row.check_out_date} · ${row.rooms_count} room(s)`
                    : `${row.service_start_date}${row.service_end_date !== row.service_start_date ? ` → ${row.service_end_date}` : ""} · guide service`}
                </p>
                {kind === "guide" && row.guide_contact_released && (
                  <p className="mt-1 inline-flex items-center gap-1 text-xs text-forest">
                    <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" /> Guide contact released (booking confirmed)
                  </p>
                )}
              </div>
              <div className="flex items-center gap-3">
                <span className="font-semibold text-ink">
                  {formatPaise(row.amount_paise, row.currency)}
                </span>
                <StatusPill status={row.status} />
                {row.status === "PENDING_PAYMENT" && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => payAndConfirm(row, kind)}
                    className="rounded-lg bg-forest px-3 py-1.5 text-xs font-semibold text-white hover:bg-forest-dark disabled:opacity-60"
                  >
                    Pay now
                  </button>
                )}
                {(row.status === "PENDING_PAYMENT" || row.status === "CONFIRMED") && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => cancel(row, kind)}
                    className="rounded-lg border border-ink/20 px-3 py-1.5 text-xs font-semibold text-ink hover:bg-ink/5 disabled:opacity-60"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </div>
          ))}
          <p className="text-xs text-ink/40">
            Payments run through the development mock gateway, clearly labelled
            &ldquo;MOCK&rdquo; — a real gateway (Razorpay) slots in behind the same interface.
          </p>
        </div>
      )}

      {/* hotel picker */}
      <section className="space-y-3">
        <h2 className="flex items-center gap-2 font-display text-xl font-semibold text-ink">
          <BedDouble className="h-5 w-5 text-forest" aria-hidden="true" /> Hotels in {city}
        </h2>
        {hotels.length === 0 && <p className="text-sm text-ink/50">No hotels listed for this city yet.</p>}
        <div className="grid gap-3 md:grid-cols-2">
          {hotels.map((h) => (
            <div key={h.id} className="rounded-xl bg-white/60 p-4 ring-1 ring-ink/10">
              <p className="font-semibold text-ink">{h.name}</p>
              <p className="mt-0.5 text-sm text-ink/60">{h.description}</p>
              <p className="mt-2 flex flex-wrap gap-1">
                {h.amenities.slice(0, 4).map((a) => (
                  <span key={a} className="rounded-full bg-ink/5 px-2 py-0.5 text-[11px] text-ink/70">
                    {a}
                  </span>
                ))}
              </p>
              <button
                type="button"
                onClick={() => (roomsFor === h.id ? setRoomsFor(null) : void openRooms(h.id))}
                className="mt-3 text-sm font-semibold text-forest underline underline-offset-4"
              >
                {roomsFor === h.id ? "Hide rooms" : "View rooms & rates"}
              </button>
              {roomsFor === h.id && (
                <div className="mt-3 space-y-2">
                  {rooms.length === 0 && <p className="text-xs text-ink/50">Loading rooms…</p>}
                  {rooms.map((r) => (
                    <div key={r.id} className="flex items-center justify-between rounded-lg bg-cream-dark/60 px-3 py-2">
                      <div>
                        <p className="text-sm font-semibold text-ink">
                          {r.name}{" "}
                          <span className="font-normal text-ink/50">· sleeps {r.capacity}</span>
                        </p>
                        <p className="text-xs text-ink/50">
                          {formatPaise(r.nightly_rate_paise, r.currency)} / night · request-based, not live availability
                        </p>
                      </div>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => setPending({ kind: "hotel", hotel: h, room: r })}
                        className="rounded-lg bg-forest px-3 py-1.5 text-xs font-semibold text-white hover:bg-forest-dark disabled:opacity-60"
                      >
                        Select
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* guides */}
      <section className="space-y-3">
        <h2 className="flex items-center gap-2 font-display text-xl font-semibold text-ink">
          <UserRound className="h-5 w-5 text-forest" aria-hidden="true" /> Verified local guides
        </h2>
        {guides.length === 0 && <p className="text-sm text-ink/50">No verified guides listed for this city yet.</p>}
        <div className="grid gap-3 md:grid-cols-2">
          {guides.map((g) => (
            <div key={g.id} className="rounded-xl bg-white/60 p-4 ring-1 ring-ink/10">
              <p className="font-semibold text-ink">
                {g.public_name}
                <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-forest/10 px-2 py-0.5 text-[10px] font-semibold text-forest">
                  <CheckCircle2 className="h-3 w-3" aria-hidden="true" /> Verified
                </span>
              </p>
              <p className="mt-0.5 text-sm text-ink/60">{g.bio}</p>
              <p className="mt-1 text-xs text-ink/50">
                {[g.city_name, ...g.languages].filter(Boolean).join(" · ")}
              </p>
              <div className="mt-3 flex items-center justify-between">
                <span className="text-sm font-semibold text-ink">
                  {g.day_rate_paise ? `${formatPaise(g.day_rate_paise, g.currency)} / day` : "Rate on request"}
                </span>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => requestGuideBooking(g)}
                  className="rounded-lg bg-forest px-3 py-1.5 text-xs font-semibold text-white hover:bg-forest-dark disabled:opacity-60"
                >
                  Book for {trip.starts_on}
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* honest placeholder for non-MVP commerce */}
      <section className="rounded-xl bg-white/60 p-4 ring-1 ring-ink/10">
        <h2 className="flex items-center gap-2 font-display text-lg font-semibold text-ink">
          <Ticket className="h-5 w-5 text-ink/40" aria-hidden="true" /> Flights &amp; entry tickets
        </h2>
        <p className="mt-1 text-sm text-ink/60">
          Flight and ticket booking is not part of the MVP schema — it arrives with
          the activities/OTA phase. Nothing here is simulated.
        </p>
      </section>

      {/* pending hotel confirm sheet */}
      {pending?.kind === "hotel" && (
        <div className="rounded-xl bg-forest/5 p-4 ring-1 ring-forest/20">
          <p className="font-semibold text-ink">
            Request {pending.room.name} at {pending.hotel.name} for{" "}
            {trip.starts_on} → {dayAfter(trip.ends_on)}?
          </p>
          <p className="mt-1 text-sm text-ink/60">
            Total {formatPaise(pending.room.nightly_rate_paise * nightsBetween(trip.starts_on, trip.ends_on), pending.room.currency)} —
            computed server-side; pay after the request is created.
          </p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <SecondaryButton type="button" onClick={() => setPending(null)} disabled={busy}>
              Not now
            </SecondaryButton>
            <PrimaryButton type="button" onClick={requestHotelBooking} disabled={busy}>
              Request booking
            </PrimaryButton>
          </div>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <SecondaryButton type="button" onClick={onBack}>
          ← Back to itinerary
        </SecondaryButton>
        <PrimaryButton type="button" disabled>
          Download itinerary PDF (coming later)
        </PrimaryButton>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    PENDING_PAYMENT: "bg-amber-100 text-amber-800",
    CONFIRMED: "bg-emerald-100 text-emerald-800",
    CANCELLED: "bg-ink/10 text-ink/60",
    COMPLETED: "bg-ink/10 text-ink/60",
    REFUNDED: "bg-ink/10 text-ink/60",
  };
  return (
    <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${map[status] ?? "bg-ink/10 text-ink/60"}`}>
      {status.replaceAll("_", " ").toLowerCase()}
    </span>
  );
}

function dayAfter(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

function nextDay(iso: string): string {
  return dayAfter(iso);
}

function nightsBetween(startIso: string, endIso: string): number {
  const a = new Date(`${startIso}T00:00:00Z`).getTime();
  const b = new Date(`${endIso}T00:00:00Z`).getTime();
  return Math.max(1, Math.round((b - a) / 86_400_000) + 1);
}
