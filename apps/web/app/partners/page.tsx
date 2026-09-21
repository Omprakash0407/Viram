"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { MapPin, Phone, Mail, Store } from "lucide-react";
import { geoApi, providersApi, type BusinessPublicRow } from "@/lib/api";

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

const CATEGORY_LABEL: Record<string, string> = {
  CAFE: "Cafés",
  RESTAURANT: "Restaurants",
  ARTISAN: "Artisans",
  HANDICRAFT: "Handicrafts",
  HOMESTAY: "Homestays",
  FOOD: "Local Food",
  TOUR: "Tours",
  EXPERIENCE: "Experiences",
  OTHER: "Other",
};

export default function PartnersPage() {
  const [items, setItems] = useState<BusinessPublicRow[] | null>(null);
  const [category, setCategory] = useState<string | null>(null);
  const [cityId, setCityId] = useState<string | null>(null);
  const [cities, setCities] = useState<Array<{ id: string; name: string }>>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    geoApi
      .cities()
      .then((res) => setCities(res.items.map((c) => ({ id: c.id, name: c.name }))))
      .catch(() => setCities([]));
  }, []);

  useEffect(() => {
    let live = true;
    setItems(null);
    setError(null);
    providersApi
      .partners({ city_id: cityId ?? undefined, category: category ?? undefined })
      .then((res) => {
        if (live) setItems(res.items);
      })
      .catch(() => {
        if (live) setError("Could not load local partners right now. Please try again.");
      });
    return () => {
      live = false;
    };
  }, [category, cityId]);

  const cityName = useMemo(
    () => new Map(cities.map((c) => [c.id, c.name])),
    [cities],
  );

  return (
    <main className="mx-auto max-w-7xl px-6 py-12">
      <header className="mb-10 max-w-2xl">
        <p className="text-sm font-semibold uppercase tracking-widest text-forest">Local Partners</p>
        <h1 className="mt-2 font-display text-4xl font-semibold text-ink">
          The people who make a place
        </h1>
        <p className="mt-3 text-ink/70">
          Cafés, artisans, homestays and local experiences — verified by the VIRĀM team and run by
          the communities you visit.
        </p>
      </header>

      {/* Filters */}
      <div className="mb-8 flex flex-wrap items-center gap-2">
        <button
          type="button"
          aria-pressed={category === null}
          onClick={() => setCategory(null)}
          className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
            category === null ? "bg-forest text-white" : "bg-white text-ink shadow-sm hover:bg-cream-dark"
          }`}
        >
          All
        </button>
        {CATEGORIES.map((c) => (
          <button
            key={c}
            type="button"
            aria-pressed={category === c}
            onClick={() => setCategory(category === c ? null : c)}
            className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
              category === c ? "bg-forest text-white" : "bg-white text-ink shadow-sm hover:bg-cream-dark"
            }`}
          >
            {CATEGORY_LABEL[c]}
          </button>
        ))}
        <select
          aria-label="Filter by city"
          value={cityId ?? ""}
          onChange={(e) => setCityId(e.target.value || null)}
          className="ml-auto rounded-full bg-white px-4 py-2 text-sm font-medium text-ink shadow-sm"
        >
          <option value="">All cities</option>
          {cities.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      {error ? (
        <p className="rounded-2xl bg-white p-6 text-sm text-ink/70 shadow-sm">{error}</p>
      ) : items === null ? (
        <p className="text-sm text-ink/50">Loading partners…</p>
      ) : items.length === 0 ? (
        <div className="rounded-2xl bg-white p-10 text-center shadow-sm">
          <Store className="mx-auto mb-3 h-8 w-8 text-ink/30" aria-hidden="true" />
          <p className="font-medium text-ink">No partners here yet</p>
          <p className="mt-1 text-sm text-ink/60">
            Businesses appear here after they register and pass verification.
          </p>
          <Link
            href="/join"
            className="mt-5 inline-block rounded-full bg-forest px-5 py-2.5 text-sm font-medium text-white hover:bg-forest-dark"
          >
            List your business
          </Link>
        </div>
      ) : (
        <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((b) => (
            <li key={b.id}>
              <Link
                href={`/partners/${b.id}`}
                className="flex h-full flex-col rounded-2xl bg-white p-6 shadow-sm transition-shadow hover:shadow-md"
              >
                <span className="w-fit rounded-full bg-cream-dark px-3 py-1 text-xs font-semibold uppercase tracking-wide text-forest">
                  {CATEGORY_LABEL[b.category] ?? b.category}
                </span>
                <h2 className="mt-3 font-display text-xl font-semibold text-ink">{b.name}</h2>
                <p className="mt-2 line-clamp-3 text-sm text-ink/70">
                  {b.description ?? "A local partner on VIRĀM."}
                </p>
                <p className="mt-auto flex items-center gap-1.5 pt-4 text-sm text-ink/60">
                  <MapPin className="h-4 w-4" aria-hidden="true" />
                  {cityName.get(b.city_id) ?? "Odisha"}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
