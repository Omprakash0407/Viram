import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronRight } from "lucide-react";
import Header from "@/app/components/Header";
import Footer from "@/app/components/Footer";
import { serverApi, type CityRow, type PlaceRow, type StateRow } from "@/lib/api";
import ExploreBrowser from "../../ExploreBrowser";

/**
 * State page — India → State → (cities + places).
 * Renders only for states with verified content in the API; everything else
 * 404s (design rule 8: destination data must be editorially documented first).
 */
export const revalidate = 60;

/** Export mode: prerender every seeded state; live mode: ISR on demand. */
export async function generateStaticParams() {
  if (!process.env.STATIC_EXPORT_BASE_PATH) return [];
  const { serverApi } = await import("@/lib/api");
  const { items } = await serverApi<{ items: Array<{ slug: string }> }>("/geo/states");
  return items.map((s) => ({ state: s.slug }));
}

export default async function ExploreStatePage({
  params,
}: {
  params: Promise<{ state: string }>;
}) {
  const { state: stateSlug } = await params;
  const states = await serverApi<{ items: StateRow[] }>("/geo/states");
  const state = states.items.find((s) => s.slug === stateSlug);
  if (!state) notFound();

  const cities = (
    await serverApi<{ items: CityRow[] }>(`/geo/cities?state_id=${state.id}`)
  ).items;
  const { items: allPlaces } = await serverApi<{ items: PlaceRow[] }>("/geo/places");
  const cityIds = new Set(cities.map((c) => c.id));
  const places = allPlaces.filter((p) => cityIds.has(p.city_id));

  return (
    <div className="bg-cream">
      <Header />
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
        <nav aria-label="Breadcrumb" className="mb-6 flex items-center gap-1 text-sm text-ink/60">
          <Link href="/explore" className="hover:underline">
            Explore
          </Link>
          <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="text-ink">{state.name}</span>
        </nav>

        <header className="mb-10">
          <p className="text-xs font-semibold tracking-[0.2em] text-ink/50">EXPLORE INDIA</p>
          <h1 className="mt-2 font-display text-4xl font-semibold text-ink sm:text-5xl">
            {state.name}
          </h1>
          <p className="mt-3 max-w-2xl text-ink/70">
            Browse cities across {state.name} — popular landmarks and verified lesser-known gems,
            curated with local communities.
          </p>
        </header>

        <ExploreBrowser
          cities={cities}
          places={places}
          selectedCitySlug={null}
          stateName={state.name}
          stateSlug={state.slug}
        />
      </div>
      <Footer />
    </div>
  );
}
