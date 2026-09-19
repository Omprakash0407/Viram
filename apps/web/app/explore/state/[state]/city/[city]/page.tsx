import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronRight } from "lucide-react";
import Header from "@/app/components/Header";
import Footer from "@/app/components/Footer";
import { serverApi, type CityRow, type PlaceRow } from "@/lib/api";
import ExploreBrowser from "../../../../ExploreBrowser";

/** States with seeded content (mirrors the live index — single source is the API). */
const LIVE_STATES = new Set(["odisha"]);

/**
 * City page — India → State → City → places.
 * Unknown city slugs and cities outside live states 404.
 */
export const revalidate = 60;

/** Export mode: prerender every seeded state×city; live mode: ISR on demand. */
export async function generateStaticParams() {
  if (!process.env.STATIC_EXPORT_BASE_PATH) return [];
  const { serverApi } = await import("@/lib/api");
  const { items: states } = await serverApi<{ items: Array<{ id: string; slug: string }> }>(
    "/geo/states",
  );
  const out: Array<{ state: string; city: string }> = [];
  for (const s of states) {
    const { items: cities } = await serverApi<{ items: Array<{ slug: string }> }>(
      `/geo/cities?state_id=${s.id}`,
    );
    for (const c of cities) out.push({ state: s.slug, city: c.slug });
  }
  return out;
}

export default async function ExploreCityPage({
  params,
}: {
  params: Promise<{ state: string; city: string }>;
}) {
  const { state: stateSlug, city: citySlug } = await params;
  if (!LIVE_STATES.has(stateSlug)) notFound();

  const states = await serverApi<{ items: Array<{ id: string; name: string; slug: string }> }>(
    "/geo/states",
  );
  const state = states.items.find((s) => s.slug === stateSlug);
  if (!state) notFound();

  const cities = (
    await serverApi<{ items: CityRow[] }>(`/geo/cities?state_id=${state.id}`)
  ).items;
  const city = cities.find((c) => c.slug === citySlug);
  if (!city) notFound();

  const { items: places } = await serverApi<{ items: PlaceRow[] }>(
    `/geo/places?city_id=${city.id}`,
  );

  return (
    <div className="bg-cream">
      <Header />
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
        <nav aria-label="Breadcrumb" className="mb-6 flex flex-wrap items-center gap-1 text-sm text-ink/60">
          <Link href="/explore" className="hover:underline">
            Explore
          </Link>
          <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
          <Link href={`/explore/state/${state.slug}`} className="hover:underline">
            {state.name}
          </Link>
          <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="text-ink">{city.name}</span>
        </nav>

        <ExploreBrowser
          cities={cities}
          places={places}
          selectedCitySlug={city.slug}
          stateName={state.name}
          stateSlug={state.slug}
        />
      </div>
      <Footer />
    </div>
  );
}
