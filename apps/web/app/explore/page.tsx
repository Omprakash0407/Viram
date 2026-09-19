import { serverApi, type CityRow, type PlaceRow } from "@/lib/api";
import Header from "@/app/components/Header";
import Footer from "@/app/components/Footer";
import ExploreBrowser from "./ExploreBrowser";

/**
 * Live mode: rendered per request (no-store fetch) + query-param filter
 * (?city=slug). Export mode (STATIC_EXPORT_BASE_PATH set): prerendered at
 * build time from VIRAM_EXPORT_API_URL, and the filter lives on
 * /explore/city/[city] instead.
 */
export default async function ExplorePage({
  searchParams,
}: {
  searchParams: Promise<{ city?: string }>;
}) {
  const { city } = process.env.STATIC_EXPORT_BASE_PATH
    ? { city: undefined }
    : await searchParams;
  const [{ items: cities }, { items: places }] = await Promise.all([
    serverApi<{ items: CityRow[] }>("/geo/cities"),
    serverApi<{ items: PlaceRow[] }>("/geo/places"),
  ]);

  return (
    <div className="bg-cream">
      <Header />
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
        <ExploreBrowser cities={cities} places={places} selectedCitySlug={city ?? null} isExport={false} />
      </div>
      <Footer />
    </div>
  );
}
