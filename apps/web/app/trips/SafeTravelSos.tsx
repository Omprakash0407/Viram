"use client";

/**
 * Safe-travel SOS panel for one trip.
 *
 * Shows the trip city's/state's/national emergency contacts, the seeded
 * emergency facilities, and — when someone on the trip is sharing their live
 * location — the fastest DRIVING route from that position to the nearest
 * hospital (real OSRM route, provider + timestamp labelled). Everything comes
 * from the admin-managed safety data (§29); nothing here is user-generated or
 * fabricated. Call buttons use tel: links; the panel never claims to contact
 * anyone by itself.
 */

import { useCallback, useEffect, useState } from "react";
import {
  Siren,
  Phone,
  Hospital,
  Navigation,
  Loader2,
  RefreshCw,
  TriangleAlert,
} from "lucide-react";
import { sosApi, type SosData } from "@/lib/api";

export default function SafeTravelSos({ tripId }: { tripId: string }) {
  const [data, setData] = useState<SosData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    (silent: boolean) => {
      if (!silent) setLoading(true);
      setError(null);
      return sosApi
        .get(tripId)
        .then((d) => setData(d))
        .catch(() =>
          setError(
            "Couldn't load emergency information right now — in a real emergency call 112 (India) directly.",
          ),
        )
        .finally(() => setLoading(false));
    },
    [tripId],
  );

  useEffect(() => {
    void load(false);
  }, [load]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-xl bg-white p-4 text-sm text-ink/60 ring-1 ring-ink/5">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Loading emergency info…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl bg-red-50 p-4 text-sm text-red-800 ring-1 ring-red-200">
        <p className="flex items-start gap-2">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /> {error}
        </p>
        <a
          href="tel:112"
          className="mt-2 inline-flex items-center gap-2 rounded-full bg-red-600 px-4 py-2 text-xs font-semibold text-white hover:bg-red-700"
        >
          <Phone className="h-3.5 w-3.5" aria-hidden="true" /> Call 112 now
        </a>
      </div>
    );
  }

  if (!data) return null;

  const { contacts, facilities, route, reference } = data;
  const national = contacts.filter((c) => c.scope === "NATIONAL");
  const local = contacts.filter((c) => c.scope !== "NATIONAL");

  return (
    <div className="rounded-xl bg-white p-4 ring-1 ring-ink/5" data-testid="sos-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 font-display text-base font-semibold text-ink">
          <Siren className="h-4 w-4 text-red-600" aria-hidden="true" />
          Safe travel SOS
        </h3>
        <button
          type="button"
          onClick={() => void load(true)}
          className="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs text-ink/50 hover:bg-ink/5 hover:text-ink/80"
          aria-label="Refresh emergency information"
        >
          <RefreshCw className="h-3 w-3" aria-hidden="true" /> Refresh
        </button>
      </div>

      {/* Nearest-hospital route — only meaningful with a live shared position */}
      {route ? (
        <div className="mt-3 rounded-lg bg-red-50 p-3 ring-1 ring-red-100">
          <p className="flex items-center gap-2 text-sm font-semibold text-red-900">
            <Hospital className="h-4 w-4 shrink-0" aria-hidden="true" />
            Nearest hospital: {route.to.name}
            {route.to.is_24x7 ? (
              <span className="rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-green-800">
                24×7
              </span>
            ) : null}
          </p>
          {reference ? (
            <p className="mt-1 text-xs text-red-800/80">
              From {reference.from}&apos;s live location ·{" "}
              {new Date(reference.updated_at).toLocaleTimeString()}
            </p>
          ) : null}
          {route.distance_km != null && route.duration_min != null ? (
            <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-red-900">
              <span className="inline-flex items-center gap-1 font-medium">
                <Navigation className="h-3 w-3" aria-hidden="true" /> {route.distance_km} km · ~
                {route.duration_min} min drive
              </span>
              <span className="text-red-700/70">
                via {route.provider} · as of {new Date(route.retrieved_at ?? "").toLocaleTimeString()}
              </span>
            </p>
          ) : (
            <p className="mt-1 text-xs text-red-800">
              Routing provider unreachable — straight-line distance ≈ {route.straight_line_km} km
              (not a driving route). Call 108 for an ambulance.
            </p>
          )}
          {route.to.phone ? (
            <a
              href={`tel:${route.to.phone}`}
              className="mt-2 inline-flex items-center gap-2 rounded-full bg-red-600 px-4 py-2 text-xs font-semibold text-white hover:bg-red-700"
            >
              <Phone className="h-3.5 w-3.5" aria-hidden="true" /> Call {route.to.name}
            </a>
          ) : null}
        </div>
      ) : (
        <p className="mt-3 rounded-lg bg-cream p-3 text-xs text-ink/60">
          No live location is being shared on this trip, so we can&apos;t compute a route to the
          nearest hospital. Anyone sharing their live location will make this panel show the
          fastest route automatically.
        </p>
      )}

      {/* Emergency numbers — national first, then city/state */}
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {[...national, ...local].map((c) => (
          <a
            key={c.label + c.phone}
            href={`tel:${c.phone}`}
            className="flex items-center justify-between gap-2 rounded-lg bg-cream px-3 py-2 text-sm text-ink hover:bg-cream-dark"
          >
            <span>
              <span className="font-medium">{c.label}</span>
              {c.scope !== "NATIONAL" ? (
                <span className="ml-1.5 text-[10px] uppercase tracking-wide text-ink/50">
                  {c.scope}
                </span>
              ) : null}
            </span>
            <span className="inline-flex items-center gap-1.5 font-semibold text-forest">
              {c.phone}
              <Phone className="h-3.5 w-3.5" aria-hidden="true" />
            </span>
          </a>
        ))}
      </div>

      {/* Facilities in the trip city */}
      {facilities.length > 0 ? (
        <ul className="mt-3 space-y-1.5">
          {facilities.map((f) => (
            <li
              key={f.id}
              className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 rounded-lg px-2 py-1.5 text-sm hover:bg-cream/60"
            >
              <span className="text-ink">
                {f.name}
                <span className="ml-2 rounded bg-ink/5 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-ink/60">
                  {f.kind.replace("_", " ")}
                </span>
                {f.is_24x7 ? (
                  <span className="ml-1.5 rounded bg-green-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-green-800">
                    24×7
                  </span>
                ) : null}
              </span>
              {f.phone ? (
                <a
                  href={`tel:${f.phone}`}
                  className="inline-flex items-center gap-1 text-xs font-medium text-forest hover:underline"
                >
                  {f.phone}
                  <Phone className="h-3 w-3" aria-hidden="true" />
                </a>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      <p className="mt-3 text-[11px] leading-relaxed text-ink/40">
        Emergency data is admin-verified, not user-generated. In a real emergency always call{" "}
        <a href="tel:112" className="font-semibold underline">
          112
        </a>{" "}
        — this panel is an aid, not a substitute.
      </p>
    </div>
  );
}
