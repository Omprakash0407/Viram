"use client";

import { useEffect, useMemo, useState } from "react";
import { CalendarDays, Loader2, MapPin, Plus, Sparkles, Trash2 } from "lucide-react";
import {
  geoApi,
  tripsApi,
  type ItineraryItemRow,
  type PlaceRow,
  type TripDetail,
} from "@/lib/api";
import type { RecommendationUI } from "./types";
import { ErrorNote, PrimaryButton, SecondaryButton } from "./wizard-ui";

function formatDay(dateIso: string): string {
  const d = new Date(dateIso);
  return d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
}

/**
 * Step 2 — the generated plan. Mirrors the mock's day-view (Day tabs +
 * Morning/Afternoon/Evening cards) and the all-itineraries overview.
 */
export function Step2Itinerary({
  trip,
  recommendations,
  runId,
  onBack,
  onProceedToBookings,
  onTripUpdated,
}: {
  trip: TripDetail;
  recommendations: RecommendationUI[];
  runId: string | null;
  onBack: () => void;
  onProceedToBookings: () => void;
  onTripUpdated?: (trip: TripDetail) => void;
}) {
  const [detail, setDetail] = useState<TripDetail>(trip);
  const [places, setPlaces] = useState<Record<string, PlaceRow>>({});
  const [activeDay, setActiveDay] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [customTitle, setCustomTitle] = useState("");

  const days = useMemo(() => detail.itinerary?.days ?? [], [detail]);
  const hasItinerary = days.length > 0;
  const day = days.find((d) => d.day_number === activeDay) ?? days[0];

  const placeIds = useMemo(() => {
    const ids = new Set<string>();
    for (const r of recommendations) ids.add(r.place_id);
    for (const d of days) for (const i of d.items) if (i.place_id) ids.add(i.place_id);
    return ids;
  }, [recommendations, days]);

  const placeKey = useMemo(() => [...placeIds].sort().join(","), [placeIds]);

  // Load names/details for every referenced place (one request, cached in state).
  useEffect(() => {
    if (!placeKey) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await geoApi.places();
        if (cancelled) return;
        const map: Record<string, PlaceRow> = {};
        for (const p of res.items) if (placeKey.split(",").includes(p.id)) map[p.id] = p;
        setPlaces((prev) => ({ ...prev, ...map }));
      } catch {
        // names stay as place IDs; non-fatal
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [placeKey]);

  async function acceptAndGenerate() {
    setError(null);
    setBusy(true);
    try {
      if (runId && recommendations.length > 0) {
        const itemIds = recommendations.filter((r) => r.id).map((r) => r.id as string);
        await tripsApi.accept(trip.id, runId, itemIds);
        await tripsApi.generateItinerary(trip.id, runId);
      } else {
        // Empty/absent recommendation run: re-run the engine (it falls back to
        // the city's best places when the moods match nothing), accept all,
        // then generate. A truly place-less city yields an empty skeleton the
        // traveller can fill with custom items.
        const rec = await tripsApi.recommendations(trip.id, true);
        if (rec.run_id && rec.items.length > 0) {
          await tripsApi.accept(trip.id, rec.run_id, []); // empty list = accept all
          await tripsApi.generateItinerary(trip.id, rec.run_id);
        } else {
          await tripsApi.generateItinerary(trip.id, null);
        }
      }
      const fresh = await tripsApi.detail(trip.id);
      setDetail(fresh);
      onTripUpdated?.(fresh);
      setActiveDay(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not build the itinerary.");
    } finally {
      setBusy(false);
    }
  }

  async function addItem(dayNumber: number) {
    const title = customTitle.trim();
    if (!title) return;
    setError(null);
    try {
      await tripsApi.addCustomItem(trip.id, dayNumber, title);
      setCustomTitle("");
      const fresh = await tripsApi.detail(trip.id);
      setDetail(fresh);
      onTripUpdated?.(fresh);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add the item.");
    }
  }

  async function removeItem(itemId: string) {
    setError(null);
    try {
      await tripsApi.removeItem(trip.id, itemId);
      const fresh = await tripsApi.detail(trip.id);
      setDetail(fresh);
      onTripUpdated?.(fresh);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove the item.");
    }
  }

  const recsForList = recommendations.slice(0, 12);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold tracking-[0.3em] text-ink/50">YOUR ITINERARY</p>
        <h1 className="mt-1 font-display text-4xl font-semibold text-ink">
          Your {detail.city?.name ?? "Custom"} Journey
        </h1>
        <p className="mt-1 text-sm text-ink/60">
          {days.length > 0
            ? `${days.length}-day journey · ${formatDay(detail.starts_on)} → ${formatDay(detail.ends_on)}`
            : "Review the personalized recommendations, then generate the day plan."}
        </p>
      </div>

      <ErrorNote message={error} />

      {/* Recommendation review (mock step 5) */}
      {!hasItinerary && (
        <section className="rounded-xl bg-white/60 p-5 ring-1 ring-ink/10">
          <h2 className="flex items-center gap-2 font-display text-xl font-semibold text-ink">
            <Sparkles className="h-5 w-5 text-forest" aria-hidden="true" /> Personalized for you
          </h2>
          <p className="mt-1 text-sm text-ink/60">
            A mix of icons and hidden gems, chosen for your mood. Generate the itinerary to lock them into days.
          </p>
          <ul className="mt-4 space-y-2">
            {recsForList.map((r, i) => {
              const p = places[r.place_id];
              const hidden = r.classification === "LESSER_KNOWN";
              return (
                <li key={r.id ?? `${r.place_id}-${i}`} className="rounded-lg bg-cream p-3 ring-1 ring-ink/5">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-semibold text-ink">{p?.name ?? "Loading…"}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                        hidden ? "bg-forest/10 text-forest" : "bg-ink/5 text-ink/60"
                      }`}
                    >
                      {hidden ? "Hidden gem" : "Popular"}
                    </span>
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-ink/60">{r.explanation}</p>
                </li>
              );
            })}
            {recsForList.length === 0 && (
              <li className="rounded-lg bg-cream p-4 text-sm text-ink/60 ring-1 ring-ink/5">
                We couldn&apos;t match your interests to catalogued places in{" "}
                {detail.city?.name ?? "this city"} yet. Generating the itinerary will fill your
                days with the city&apos;s best places instead — or go back and pick a different
                combination of interests.
              </li>
            )}
          </ul>
          <div className="mt-4">
            <PrimaryButton onClick={() => void acceptAndGenerate()} disabled={busy}>
              {busy ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Building days…
                </span>
              ) : recsForList.length === 0 ? (
                "Generate Itinerary from the city's best places →"
              ) : (
                "Generate Itinerary →"
              )}
            </PrimaryButton>
          </div>
        </section>
      )}

      {/* Day tabs + detail (mock day view) */}
      {hasItinerary && (
        <>
          <div className="flex flex-wrap gap-2">
            {days.map((d) => (
              <button
                key={d.day_number}
                type="button"
                aria-pressed={activeDay === d.day_number}
                onClick={() => setActiveDay(d.day_number)}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  activeDay === d.day_number ? "bg-forest text-white" : "bg-white text-ink ring-1 ring-ink/15 hover:bg-cream-dark"
                }`}
              >
                Day {d.day_number}
              </button>
            ))}
          </div>

          {day && (
            <section className="rounded-xl bg-white/60 p-5 ring-1 ring-ink/10">
              <h2 className="font-display text-2xl font-semibold text-ink">
                Day {day.day_number}: {formatDay(day.date)}
              </h2>
              <ul className="mt-4 space-y-3">
                {day.items.map((item: ItineraryItemRow) => {
                  const p = item.place_id ? places[item.place_id] : undefined;
                  return (
                    <li key={item.id} className="flex items-start justify-between gap-4 rounded-lg bg-cream p-4 ring-1 ring-ink/5">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-ink">{item.title}</p>
                        {p && (
                          <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink/60">
                            <span className="inline-flex items-center gap-1">
                              <MapPin className="h-3 w-3" aria-hidden="true" />
                              {p.classification === "LESSER_KNOWN" ? "Hidden gem" : "Popular"}
                            </span>
                            {p.typical_visit_minutes != null && (
                              <span className="inline-flex items-center gap-1">
                                <CalendarDays className="h-3 w-3" aria-hidden="true" />~{p.typical_visit_minutes} min
                              </span>
                            )}
                          </p>
                        )}
                        {item.note && <p className="mt-1 text-xs text-ink/50">{item.note}</p>}
                      </div>
                      <button
                        type="button"
                        onClick={() => void removeItem(item.id)}
                        aria-label={`Remove ${item.title}`}
                        className="rounded-md p-2 text-ink/40 transition-colors hover:bg-red-50 hover:text-red-600"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </li>
                  );
                })}
                {day.items.length === 0 && (
                  <li className="rounded-lg bg-cream p-4 text-sm text-ink/50 ring-1 ring-ink/5">
                    A lighter day — add an experience below.
                  </li>
                )}
              </ul>

              {/* Add custom experience (mock "customize") */}
              <div className="mt-4 flex gap-2">
                <input
                  value={customTitle}
                  onChange={(e) => setCustomTitle(e.target.value)}
                  placeholder="Add your own (e.g. Café stop, evening walk)…"
                  aria-label={`Add custom item to day ${day.day_number}`}
                  className="w-full rounded-lg border border-ink/15 bg-white px-3 py-2.5 text-sm outline-none focus:border-forest"
                />
                <button
                  type="button"
                  onClick={() => void addItem(day.day_number)}
                  disabled={!customTitle.trim()}
                  className="inline-flex items-center gap-2 rounded-lg bg-forest px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-forest-dark disabled:opacity-50"
                >
                  <Plus className="h-4 w-4" aria-hidden="true" /> Add
                </button>
              </div>
            </section>
          )}
        </>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <SecondaryButton type="button" onClick={onBack}>
          ← Back to Preferences
        </SecondaryButton>
        <PrimaryButton type="button" onClick={onProceedToBookings} disabled={!hasItinerary}>
          Proceed to Bookings →
        </PrimaryButton>
      </div>
    </div>
  );
}
