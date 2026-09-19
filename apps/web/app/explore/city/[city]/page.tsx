import { notFound } from "next/navigation";
import { serverApi, type CityRow, type PlaceRow } from "@/lib/api";
import Header from "@/app/components/Header";
import Footer from "@/app/components/Footer";
import ExploreBrowser from "../../ExploreBrowser";

/**
 * Export-only route backing the frozen city-filter links on GitHub Pages
 * (/Viram/explore/city/puri/ …). Query-param links can't be navigated to on
 * static hosting, so export builds prerender one page per city. Never built in
 * live mode (where the index filter uses ?city=).
 */
export async function generateStaticParams() {
  if (!process.env.STATIC_EXPORT_BASE_PATH) return [];
  const { serverApi } = await import("@/lib/api");
  const { items } = await serverApi<{ items: CityRow[] }>("/geo/cities");
  return items.map((c) => ({ city: c.slug }));
}

export default async function ExploreCityPage({
  params,
}: {
  params: Promise<{ city: string }>;
}) {
  const { city: slug } = await params;
  const [{ items: cities }, { items: places }] = await Promise.all([
    serverApi<{ items: CityRow[] }>("/geo/cities"),
    serverApi<{ items: PlaceRow[] }>("/geo/places"),
  ]);
  if (!cities.some((c) => c.slug === slug)) notFound();

  return (
    <div className="bg-cream">
      <Header />
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
        <ExploreBrowser cities={cities} places={places} selectedCitySlug={slug} isExport />
      </div>
      <Footer />
    </div>
  );
}
