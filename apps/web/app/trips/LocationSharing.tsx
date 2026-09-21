"use client";

/**
 * Opt-in live-location sharing for one trip (beta).
 *
 * Consent first: nothing happens until the traveller flips the toggle. When
 * on, the browser's GPS sends a heartbeat every ~20 s via navigator.
 * geolocation.watchPosition; the toggle off (or leaving the page) deletes the
 * share row server-side, so companions stop seeing the traveller instantly.
 * GPS points live at most one day past trip end (server-enforced purge_date).
 */

import { useEffect, useRef, useState } from "react";
import { MapPin, Loader2 } from "lucide-react";
import { locationApi } from "@/lib/api";

const HEARTBEAT_MS = 20_000;

export default function LocationSharing({ tripId }: { tripId: string }) {
  const [sharing, setSharing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const watchId = useRef<number | null>(null);
  const lastSent = useRef(0);
  const lastFix = useRef<{ lat: number; lng: number; acc: number | null } | null>(null);

  // stop sharing if the traveller leaves while the toggle is on
  useEffect(() => {
    return () => {
      if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current);
      if (sharing) void locationApi.stop(tripId).catch(() => undefined);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- stop() must see the latest sharing state; tripId is fixed
  }, [tripId, sharing]);

  function sendHeartbeat() {
    const fix = lastFix.current;
    if (!fix) return;
    const now = Date.now();
    if (now - lastSent.current < HEARTBEAT_MS) return;
    lastSent.current = now;
    void locationApi
      .share(tripId, fix.lat, fix.lng, fix.acc ?? undefined)
      .catch(() => setMsg("Couldn't reach the server — your location isn't being shared right now."));
  }

  async function startSharing() {
    if (!("geolocation" in navigator)) {
      setMsg("This browser doesn't support location sharing.");
      return;
    }
    setBusy(true);
    setMsg(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        lastFix.current = {
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          acc: pos.coords.accuracy,
        };
        lastSent.current = 0;
        void locationApi
          .share(tripId, pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy)
          .then(() => {
            watchId.current = navigator.geolocation.watchPosition((p) => {
              lastFix.current = {
                lat: p.coords.latitude,
                lng: p.coords.longitude,
                acc: p.coords.accuracy,
              };
              sendHeartbeat();
            });
            setSharing(true);
            setMsg(null);
          })
          .catch(() => setMsg("Couldn't start sharing — try again."))
          .finally(() => setBusy(false));
      },
      (err) => {
        setBusy(false);
        setMsg(
          err.code === err.PERMISSION_DENIED
            ? "Location permission was denied — allow it in your browser's address bar to share."
            : err.code === err.POSITION_UNAVAILABLE
              ? "Your position isn't available right now — try again outdoors or with better signal."
              : "Getting your location timed out — try again.",
        );
      },
      { enableHighAccuracy: true, timeout: 12_000, maximumAge: 5_000 },
    );
  }

  async function stopSharing() {
    setBusy(true);
    if (watchId.current !== null) {
      navigator.geolocation.clearWatch(watchId.current);
      watchId.current = null;
    }
    try {
      await locationApi.stop(tripId);
      setSharing(false);
      setMsg(null);
    } catch {
      setMsg("Couldn't stop sharing — try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl bg-white p-4 ring-1 ring-ink/5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 font-display text-base font-semibold text-ink">
            <MapPin className="h-4 w-4 text-forest" aria-hidden="true" />
            Share live location <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-amber-800">beta</span>
          </h3>
          <p className="mt-1 max-w-md text-xs text-ink/60">
            {sharing
              ? "Sharing with your travel companions on this trip. Turn off anytime; points auto-delete a day after the trip ends."
              : "Opt-in only. Your companions on this trip can see where you are while you travel together — nobody else can."}
          </p>
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={() => void (sharing ? stopSharing() : startSharing())}
          aria-pressed={sharing}
          className={`flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors ${
            sharing
              ? "bg-red-50 text-red-700 ring-1 ring-red-200 hover:bg-red-100"
              : "bg-forest text-white hover:bg-forest-dark"
          } disabled:opacity-60`}
        >
          {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          {sharing ? "Stop sharing" : "Share my location"}
        </button>
      </div>
      {msg ? <p className="mt-2 text-xs text-red-700">{msg}</p> : null}
    </div>
  );
}
