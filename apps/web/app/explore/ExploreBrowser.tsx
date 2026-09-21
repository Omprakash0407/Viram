"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronUp, MapPin, Search, Star } from "lucide-react";
import type { CityRow, PlaceRow } from "@/lib/api";
import { gradientFor } from "./gradient";

/** Curated cover photos exist only for the three mocked places (so far). */
const PLACE_COVER: Record<string, string> = {
  "chilika-lake-satapada-side": "/images/places/chilika-lake-satapada-side/hero.jpg",
  "raghurajpur-heritage-village": "/images/places/raghurajpur-heritage-village/hero.jpg",
  "baliharachandi-beach": "/images/places/baliharachandi-beach/hero.jpg",
};

/** Theme tabs group the place categories into traveller-facing moods. */
const THEMES: Array<{ key: string; label: string; blurb: string; categories: string[] }> = [
  {
    key: "culture",
    label: "Culture",
    blurb: "Temples, crafts, festivals and living traditions.",
    categories: ["heritage", "culture", "food", "crafts"],
  },
  {
    key: "city-life",
    label: "City Life",
    blurb: "Markets, parks, museums and evening fun.",
    categories: ["fun", "markets", "museums", "city-life"],
  },
  {
    key: "nature",
    label: "Nature",
    blurb: "Lakes, forests, wildlife and scenic calm.",
    categories: ["nature", "scenic", "lakes", "wildlife", "adventure", "trekking", "parks"],
  },
];

/** Quarter-of-year travel guidance for Odisha (editorial, honest guidance). */
const QUARTER_TIPS: Record<number, { title: string; body: string }> = {
  1: {
    title: "Jan – Mar · peak season",
    body: "Cool, dry and festival-rich — ideal for beaches, Chilika dolphins and heritage walks. Book popular stays early.",
  },
  2: {
    title: "Apr – Jun · rising heat",
    body: "Temperatures climb; plan mornings, hill escapes like Daringbadi, and keep afternoons light.",
  },
  3: {
    title: "Jul – Sep · monsoon green",
    body: "Lush landscapes and full waterfalls — great for nature and scenic drives; carry rain gear and check road conditions.",
  },
  4: {
    title: "Oct – Dec · festive opener",
    body: "Weather cools and the festival calendar fills — a fine quarter for culture trails and the start of beach season.",
  },
};

const QUARTER_FILTERS = [
  { q: 1, label: "Jan – Mar" },
  { q: 2, label: "Apr – Jun" },
  { q: 3, label: "Jul – Sep" },
  { q: 4, label: "Oct – Dec" },
];

const PREVIEW_COUNT = 3;

/**
 * The Explore browser: search + theme tabs + city filter + quarter suggestion,
 * with a 3-place preview per theme and a See-more expansion.
 */
export default function ExploreBrowser({
  cities,
  places,
  stateName = "Odisha",
  stateSlug = "odisha",
}: {
  cities: CityRow[];
  places: PlaceRow[];
  stateName?: string;
  stateSlug?: string;
}) {
  const [query, setQuery] = useState("");
  const [theme, setTheme] = useState<string | null>("culture");
  const [expanded, setExpanded] = useState(false);
  const [selectedCitySlug, setSelectedCitySlug] = useState<string | null>(null);
  const [quarterView, setQuarterView] = useState<number>(
    Math.floor(new Date().getMonth() / 3) + 1,
  );

  const cityById = useMemo(() => new Map(cities.map((c) => [c.id, c])), [cities]);
  const tip = QUARTER_TIPS[quarterView];

  /** Live combo counts, used to dim filters that would produce zero results. */
  const countFor = useMemo(() => {
    const idBySlug = new Map(cities.map((c) => [c.slug, c.id]));
    return (citySlug: string | null, themeKey: string | null) => {
      const cid = citySlug ? idBySlug.get(citySlug) : null;
      const cats = THEMES.find((t) => t.key === themeKey)?.categories;
      return places.filter(
        (p) => (!cid || p.city_id === cid) && (!cats || (p.category && cats.includes(p.category))),
      ).length;
    };
  }, [places, cities]);

  const selectedCityName = cities.find((c) => c.slug === selectedCitySlug)?.name ?? null;
  const activeThemeLabel = THEMES.find((t) => t.key === theme)?.label ?? null;

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const themeDef = THEMES.find((t) => t.key === theme);
    // Chips carry slugs; places carry city UUIDs — resolve before comparing
    // (a raw slug-vs-id compare can never match and silently empties the grid).
    const selectedCityId = cities.find((c) => c.slug === selectedCitySlug)?.id ?? null;
    return places.filter((p) => {
      if (selectedCityId && p.city_id !== selectedCityId) return false;
      if (
        themeDef &&
        !(p.category && themeDef.categories.includes(p.category))
      )
        return false;
      if (q && !(`${p.name} ${p.description ?? ""}`.toLowerCase().includes(q))) return false;
      return true;
    });
  }, [places, query, theme, selectedCitySlug, cities]);

  const sorted = useMemo(
    () =>
      [...filtered].sort(
        (a, b) =>
          (b.rating_avg ?? 0) - (a.rating_avg ?? 0) ||
          (b.popularity_score ?? 0) - (a.popularity_score ?? 0),
      ),
    [filtered],
  );

  const themePlaceCount = sorted.length;
  const visible = expanded ? sorted : sorted.slice(0, PREVIEW_COUNT);

  return (
    <div>
      {/* Search + quarter suggestion */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink/40" aria-hidden="true" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search places in this state…"
            aria-label="Search places"
            className="w-full rounded-full border border-ink/15 bg-white py-3 pl-11 pr-4 text-sm outline-none focus:border-forest"
          />
        </div>
        {tip && (
          <div className="rounded-2xl bg-forest/5 px-4 py-3 ring-1 ring-forest/15 sm:max-w-md">
            <p className="text-xs font-semibold uppercase tracking-wide text-forest">{tip.title}</p>
            <p className="mt-0.5 text-xs text-ink/70">{tip.body}</p>
          </div>
        )}
      </div>

      {/* Theme tabs (All + traveller-facing moods) */}
      <nav aria-label="Filter by theme" className="mb-5 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => {
            setTheme(null);
            setExpanded(false);
          }}
          aria-pressed={theme === null}
          className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
            theme === null
              ? "bg-forest text-white"
              : "border border-ink/15 text-ink/80 hover:border-forest hover:text-forest"
          }`}
        >
          All
        </button>
        {THEMES.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => {
              setTheme(theme === t.key ? null : t.key);
              setExpanded(false);
            }}
            aria-pressed={theme === t.key}
            disabled={theme !== t.key && !!selectedCitySlug && countFor(selectedCitySlug, t.key) === 0}
            title={
              theme !== t.key && selectedCitySlug && countFor(selectedCitySlug, t.key) === 0
                ? `No ${t.label.toLowerCase()} places in ${selectedCityName ?? "this city"} yet`
                : undefined
            }
            className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
              theme === t.key
                ? "bg-forest text-white"
                : "border border-ink/15 text-ink/80 hover:border-forest hover:text-forest disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:border-ink/15 disabled:hover:text-ink/80"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {/* Quarter filter: selects which season's guidance is shown */}
      <nav aria-label="Filter by travel season" className="mb-5 flex flex-wrap items-center gap-2">
        <span className="mr-1 text-xs font-semibold uppercase tracking-wide text-ink/50">
          When
        </span>
        {QUARTER_FILTERS.map((f) => (
          <button
            key={f.q}
            type="button"
            onClick={() => setQuarterView(f.q)}
            aria-pressed={quarterView === f.q}
            className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors ${
              quarterView === f.q
                ? "bg-ink text-white"
                : "border border-ink/15 text-ink/70 hover:border-forest hover:text-forest"
            }`}
          >
            {f.label}
          </button>
        ))}
      </nav>

      {/* City chips */}
      <nav aria-label="Filter by city" className="mb-8 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setSelectedCitySlug(null)}
          aria-pressed={!selectedCitySlug}
          className={`rounded-full px-4 py-2 text-sm font-medium ${
            !selectedCitySlug ? "bg-ink text-white" : "border border-ink/15 text-ink/80 hover:border-forest"
          }`}
        >
          All cities
        </button>
        {cities.map((c) => {
          const emptyUnderTheme = !!theme && countFor(c.slug, theme) === 0;
          return (
            <button
              key={c.id}
              type="button"
              onClick={() => {
                setSelectedCitySlug(selectedCitySlug === c.slug ? null : c.slug);
                setExpanded(false);
              }}
              aria-pressed={selectedCitySlug === c.slug}
              disabled={selectedCitySlug !== c.slug && emptyUnderTheme}
              title={
                selectedCitySlug !== c.slug && emptyUnderTheme
                  ? `No ${activeThemeLabel?.toLowerCase() ?? "matching"} places in ${c.name} yet`
                  : undefined
              }
              className={`rounded-full px-4 py-2 text-sm font-medium ${
                selectedCitySlug === c.slug
                  ? "bg-ink text-white"
                  : "border border-ink/15 text-ink/80 hover:border-forest disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:border-ink/15"
              }`}
            >
              {c.name}
            </button>
          );
        })}
      </nav>

      {/* Results */}
      <p className="mb-4 text-sm text-ink/60">
        {theme
          ? `${THEMES.find((t) => t.key === theme)?.blurb} · `
          : "All themes · "}
        {themePlaceCount} place{themePlaceCount === 1 ? "" : "s"}
      </p>

      <ul className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {visible.map((p) => {
          const city = cityById.get(p.city_id);
          const cover = PLACE_COVER[p.slug];
          return (
            <li key={p.id} className="group">
              <Link
                href={`/explore/${p.slug}`}
                className="block overflow-hidden rounded-2xl bg-white shadow-md ring-1 ring-ink/5 transition-shadow hover:shadow-xl"
              >
                <div className="relative aspect-[16/10] overflow-hidden">
                  {cover ? (
                    // eslint-disable-next-line @next/next/no-img-element -- curated static asset
                    <img
                      src={cover}
                      alt={p.name}
                      className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                    />
                  ) : (
                    <div
                      role="img"
                      aria-label={p.name}
                      className="flex h-full w-full items-end p-4 transition-transform duration-500 group-hover:scale-105"
                      style={{ background: gradientFor(p.slug) }}
                    >
                      <span className="rounded-full bg-white/85 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-ink/70">
                        {city?.name ?? stateName}
                      </span>
                    </div>
                  )}
                  {p.classification === "LESSER_KNOWN" && (
                    <span className="absolute left-3 top-3 rounded-full bg-forest px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-white shadow">
                      Hidden gem
                    </span>
                  )}
                </div>
                <div className="p-5">
                  <h2 className="font-display text-lg font-semibold text-ink">{p.name}</h2>
                  <p className="mt-1 flex items-center gap-1.5 text-sm text-ink/60">
                    <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
                    {city ? `${city.name}, ${stateName}` : stateName}
                  </p>
                  <p className="mt-2 line-clamp-2 text-sm text-ink/70">
                    {p.lesser_known_note ?? p.description}
                  </p>
                  <p className="mt-3 flex items-center gap-1 text-sm font-medium text-ink">
                    <Star className="h-4 w-4 fill-amber-500 text-amber-500" aria-hidden="true" />
                    {p.rating_avg ? p.rating_avg.toFixed(1) : "New"}
                    {(p.review_count ?? 0) > 0 && (
                      <span className="font-normal text-ink/50">· {p.review_count} reviews</span>
                    )}
                    {p.typical_visit_minutes ? (
                      <span className="ml-2 font-normal text-ink/50">
                        · ~{p.typical_visit_minutes} min visit
                      </span>
                    ) : null}
                  </p>
                </div>
              </Link>
            </li>
          );
        })}
      </ul>

      {visible.length === 0 && (
        <div className="mt-12 rounded-2xl bg-white p-8 text-center ring-1 ring-ink/10">
          <p className="font-display text-lg font-semibold text-ink">
            No places match this combination yet
          </p>
          <p className="mx-auto mt-2 max-w-md text-sm text-ink/60">
            {[
              selectedCityName ? `in ${selectedCityName}` : null,
              activeThemeLabel ? `for “${activeThemeLabel}”` : null,
              query.trim() ? `matching “${query.trim()}”` : null,
            ]
              .filter(Boolean)
              .join(" ") || "with the current filters"}
            . VIRĀM adds places only after they are verified with local communities — this
            combination may fill in later.
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            {selectedCitySlug && (
              <button
                type="button"
                onClick={() => {
                  setTheme(null);
                  setExpanded(false);
                }}
                className="rounded-full bg-forest px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-forest-dark"
              >
                Show all themes in {selectedCityName}
              </button>
            )}
            {theme && (
              <button
                type="button"
                onClick={() => {
                  setSelectedCitySlug(null);
                  setExpanded(false);
                }}
                className="rounded-full bg-forest px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-forest-dark"
              >
                Show {activeThemeLabel} across {stateName}
              </button>
            )}
            {query.trim() && (
              <button
                type="button"
                onClick={() => setQuery("")}
                className="rounded-full border border-ink/15 px-4 py-2 text-sm font-semibold text-ink/80 transition-colors hover:border-forest hover:text-forest"
              >
                Clear search
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                setQuery("");
                setTheme(null);
                setSelectedCitySlug(null);
                setExpanded(false);
              }}
              className="rounded-full border border-ink/15 px-4 py-2 text-sm font-semibold text-ink/80 transition-colors hover:border-forest hover:text-forest"
            >
              Reset all filters
            </button>
          </div>
        </div>
      )}

      {themePlaceCount > PREVIEW_COUNT && (
        <div className="mt-8 text-center">
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
            className="inline-flex items-center gap-2 rounded-full border border-forest px-6 py-3 text-sm font-semibold text-forest transition-colors hover:bg-forest hover:text-white"
          >
            {expanded ? (
              <>
                Show fewer <ChevronUp className="h-4 w-4" aria-hidden="true" />
              </>
            ) : (
              <>
                See more places ({themePlaceCount - PREVIEW_COUNT}){" "}
                <ChevronDown className="h-4 w-4" aria-hidden="true" />
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
