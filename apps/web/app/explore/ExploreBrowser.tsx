import Link from "next/link";
import { MapPin, Star } from "lucide-react";
import type { CityRow, PlaceRow } from "@/lib/api";
import { gradientFor } from "./gradient";

/** Curated cover photos exist only for the three mocked places (so far). */
const PLACE_COVER: Record<string, string> = {
  "chilika-lake-satapada-side": "/images/places/chilika-lake-satapada-side/hero.jpg",
  "raghurajpur-heritage-village": "/images/places/raghurajpur-heritage-village/hero.jpg",
  "baliharachandi-beach": "/images/places/baliharachandi-beach/hero.jpg",
};

/**
 * The Explore grid: city filter chips + place cards. Shared by the state page
 * (all of the state's places) and the city page (one city, filter locked to
 * that city).
 */
export default function ExploreBrowser({
  cities,
  places,
  selectedCitySlug,
  stateName = "Odisha",
  stateSlug = "odisha",
}: {
  cities: CityRow[];
  places: PlaceRow[];
  selectedCitySlug: string | null;
  stateName?: string;
  stateSlug?: string;
}) {
  const cityById = new Map(cities.map((c) => [c.id, c]));
  const sorted = [...places].sort(
    (a, b) =>
      (b.rating_avg ?? 0) - (a.rating_avg ?? 0) ||
      (b.popularity_score ?? 0) - (a.popularity_score ?? 0),
  );
  const selectedCity =
    selectedCitySlug != null ? cities.find((c) => c.slug === selectedCitySlug) ?? null : null;
  const visible = selectedCity ? sorted.filter((p) => p.city_id === selectedCity.id) : sorted;
  const cityHref = (slug: string) => `/explore/state/${stateSlug}/city/${slug}`;

  return (
    <>
      <header className="mb-10">
        <p className="text-xs font-semibold tracking-[0.2em] text-ink/50">
          {selectedCity ? selectedCity.name.toUpperCase() : `EXPLORE ${stateName.toUpperCase()}`}
        </p>
        <h1 className="mt-2 font-display text-4xl font-semibold text-ink sm:text-5xl">
          Places worth the pause.
        </h1>
        <p className="mt-3 max-w-2xl text-ink/70">
          Popular landmarks and verified lesser-known gems, curated with local communities. Every
          &quot;hidden gem&quot; here is editorially documented — never invented.
        </p>
      </header>

      <nav aria-label="Filter by city" className="mb-8 flex flex-wrap gap-2">
        <Link
          href="/explore"
          className={`rounded-full px-4 py-2 text-sm font-medium ${
            !selectedCity
              ? "bg-forest text-white"
              : "border border-ink/15 text-ink/80 transition-colors hover:border-forest hover:text-forest"
          }`}
        >
          All
        </Link>
        {cities.map((c) => (
          <Link
            key={c.id}
            href={cityHref(c.slug)}
            className={`rounded-full px-4 py-2 text-sm font-medium ${
              selectedCity?.id === c.id
                ? "bg-forest text-white"
                : "border border-ink/15 text-ink/80 transition-colors hover:border-forest hover:text-forest"
            }`}
          >
            {c.name}
          </Link>
        ))}
      </nav>

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
                        {city?.name ?? "Odisha"}
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
        <p className="mt-12 text-center text-sm text-ink/50">
          No places catalogued for this city yet.
        </p>
      )}

      <p className="mt-12 text-center text-sm text-ink/50">
        Rich detail pages — experiences, travel tips, photos and nearby places — are live for
        Chilika (Satapada), Raghurajpur and Baliharachandi. More places get curated pages as
        content is verified.
      </p>
    </>
  );
}
