"use client";

/**
 * Live companions map (beta) — Leaflet + OpenStreetMap tiles (free, no key).
 * Plotted: the OTHER sharing members of this trip, refreshed on an interval
 * while mounted. The viewer's own GPS never renders here — only what the API
 * returns (the backend never echoes your own position back).
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, Marker, Popup, TileLayer, Circle } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { locationApi, type CompanionLocation } from "@/lib/api";

const REFRESH_MS = 20_000; // poll interval; the backend drops heartbeats >15 min old

function companionIcon(label: string) {
  return L.divIcon({
    className: "",
    html: `<span style="display:flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:999px;background:#1e3a2f;color:#f4f0e8;font:600 13px system-ui,sans-serif;border:2px solid #f4f0e8;box-shadow:0 2px 6px rgba(0,0,0,.35)">${label}</span>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  });
}

export default function CompanionsMap({ tripId }: { tripId: string }) {
  const [companions, setCompanions] = useState<CompanionLocation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await locationApi.companions(tripId);
        if (cancelled) return;
        setCompanions(data.items);
        setError(null);
      } catch {
        if (!cancelled) setError("Live locations are unavailable right now.");
      }
    }

    void load();
    timer.current = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      if (timer.current) clearInterval(timer.current);
    };
  }, [tripId]);

  // fit bounds once the first batch arrives
  const center = useMemo(() => {
    if (!companions || companions.length === 0) return null;
    const lat = companions.reduce((s, c) => s + c.latitude, 0) / companions.length;
    const lng = companions.reduce((s, c) => s + c.longitude, 0) / companions.length;
    return [lat, lng] as [number, number];
  }, [companions]);

  if (error) {
    return <p className="mt-2 text-sm text-ink/60">{error}</p>;
  }
  if (companions !== null && companions.length === 0) {
    return (
      <p className="mt-2 text-sm text-ink/60">
        No one is sharing their location on this trip yet. Each traveller can turn
        on sharing from their own trip panel — you&apos;ll see them here, live.
      </p>
    );
  }
  if (companions === null || center === null) {
    return <p className="mt-2 text-sm text-ink/50">Loading live map…</p>;
  }

  return (
    <div className="mt-3 overflow-hidden rounded-xl ring-1 ring-ink/10">
      <MapContainer
        center={center}
        zoom={13}
        scrollWheelZoom={false}
        style={{ height: 320, width: "100%" }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {companions.map((c, i) => (
          <div key={c.user_id}>
            <Marker position={[c.latitude, c.longitude]} icon={companionIcon(c.display_name.slice(0, 1).toUpperCase())}>
              <Popup>
                <strong>{c.display_name}</strong>
                <br />
                last update: {new Date(c.updated_at).toLocaleTimeString("en-IN")}
                {c.accuracy_m != null ? <><br />±{c.accuracy_m} m</> : null}
              </Popup>
            </Marker>
            {c.accuracy_m != null ? (
              <Circle
                center={[c.latitude, c.longitude]}
                radius={Math.min(c.accuracy_m, 500)}
                pathOptions={{ color: "#1e3a2f", weight: 1, fillOpacity: 0.08 }}
              />
            ) : null}
          </div>
        ))}
      </MapContainer>
    </div>
  );
}
