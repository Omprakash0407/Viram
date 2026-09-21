import Link from "next/link";
import { notFound } from "next/navigation";
import {
  Check,
  ChevronRight,
  MapPin,
  Navigation,
  Palette,
  Ship,
  Bird,
  Camera,
  Mountain,
  Waves,
  Landmark,
  UtensilsCrossed,
  Sun,
  Star,
  Bookmark,
  ArrowRight,
} from "lucide-react";
import { serverApi, type PlaceDetail } from "@/lib/api";
import Header from "@/app/components/Header";
import Footer from "@/app/components/Footer";
import PlaceImage from "../PlaceImage";
import ReviewsSection from "./ReviewsSection";

/**
 * ISR: prerendered/cached and revalidated every 60s — place details change
 * only via seeds/admin, so a minute of staleness is fine in live mode. Static
 * export prerenders once at build time. (A no-store fetch here crashes the
 * SSG route with DYNAMIC_SERVER_USAGE at runtime.)
 */
export const revalidate = 60;

/**
 * Export mode: prerender every place at build time (generateStaticParams).
 * Live mode: rendered per request (no-store fetch; place data is edited via
 * seeds/admin).
 */
export async function generateStaticParams() {
  if (!process.env.STATIC_EXPORT_BASE_PATH) return [];
  const { serverApi } = await import("@/lib/api");
  const { items } = await serverApi<{ items: { slug: string }[] }>("/geo/places");
  return items.map((p) => ({ slug: p.slug }));
}

const EXPERIENCE_ICONS = [Ship, Bird, Camera, Palette, Waves, Mountain, Landmark, UtensilsCrossed, Sun];

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  try {
    const place = await serverApi<PlaceDetail>(`/geo/places/${encodeURIComponent(slug)}`);
    return { title: `${place.name} — Explore | VIRĀM` };
  } catch {
    return { title: "Place not found | VIRĀM" };
  }
}

export default async function PlaceDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  let place: PlaceDetail;
  try {
    place = await serverApi<PlaceDetail>(`/geo/places/${encodeURIComponent(slug)}`);
  } catch (err) {
    if ((err as { status?: number }).status === 404) notFound();
    throw err;
  }

  const d = place.details;
  const mapsUrl = `https://www.google.com/maps?q=${place.latitude},${place.longitude}`;
  const tabs = ["Overview", "Experiences", "Travel Info", "Photos & Videos", "Reviews", "Nearby"];
  const infoRows: [string, string | undefined][] = d?.travel_info
    ? [
        ["Location", d.travel_info.location],
        ["Distance", d.travel_info.distance],
        ["Best Time to Visit", d.travel_info.best_time],
        ["Weather", d.travel_info.weather],
        ["Ideal For", d.travel_info.ideal_for],
      ]
    : [];

  return (
    <div className="bg-cream">
      <Header />
      {/* ---------- Hero ---------- */}
      <section className="relative h-[420px] overflow-hidden sm:h-[480px]">
        <PlaceImage slug={place.slug} kind="hero" alt={place.name} priority className="absolute inset-0 h-full w-full object-cover" />
        <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/20 to-black/30" />
        <div className="relative mx-auto flex h-full max-w-7xl flex-col justify-end px-4 pb-8 sm:px-6">
          <nav aria-label="Breadcrumb" className="mb-4 flex flex-wrap items-center gap-1 text-sm text-white/85">
            <Link href="/explore" className="hover:underline">Explore</Link>
            <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
            <Link href={`/explore/state/${place.state.slug}`} className="hover:underline">{place.state.name}</Link>
            <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
            <Link href={`/explore/state/${place.state.slug}/city/${place.city.slug}`} className="hover:underline">{place.city.name}</Link>
            <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="text-white">{place.name}</span>
          </nav>
          {d?.eyebrow && (
            <p className="text-xs font-semibold tracking-[0.25em] text-white/85">{d.eyebrow}</p>
          )}
          <h1 className="mt-2 max-w-3xl font-display text-4xl font-semibold text-white sm:text-6xl">
            {place.name}
          </h1>
          <p className="mt-3 max-w-xl text-white/90">{d?.tagline ?? place.description}</p>
          <p className="mt-3 flex items-center gap-1.5 text-sm text-white/80">
            <MapPin className="h-4 w-4" aria-hidden="true" />
            {d?.travel_info?.location ?? `${place.city.name}, ${place.state.name}`}
          </p>
          {d?.accent_script && (
            <p className="absolute right-4 top-24 hidden max-w-[16ch] rotate-2 font-display text-2xl italic text-white sm:right-10 sm:top-28 sm:block">
              {d.accent_script}
            </p>
          )}
          {place.classification === "LESSER_KNOWN" && (
            <span className="absolute right-4 top-6 rounded-full bg-cream px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-forest sm:right-10">
              Hidden gem
            </span>
          )}
        </div>
      </section>

      {/* ---------- Tab bar ---------- */}
      <div className="sticky top-0 z-20 border-b border-ink/10 bg-cream/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
          <nav aria-label="Page sections" className="flex gap-1 overflow-x-auto py-3">
            {tabs.map((t) => (
              <a
                key={t}
                href={`#${t.toLowerCase().replace(/[^a-z]+/g, "-")}`}
                className="whitespace-nowrap rounded-full px-4 py-2 text-sm font-medium text-ink/70 transition-colors hover:bg-forest hover:text-white"
              >
                {t}
              </a>
            ))}
          </nav>
          <div className="hidden items-center gap-3 py-2 sm:flex">
            <Bookmark className="h-5 w-5 text-ink/60" aria-hidden="true" />
            <Link
              href="/plan"
              className="flex items-center gap-2 rounded-full bg-forest px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-forest-dark"
            >
              Add to Trip Plan <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </div>

      {/* ---------- About ---------- */}
      <section id="overview" className="mx-auto max-w-7xl scroll-mt-24 px-4 py-12 sm:px-6">
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-[1.1fr_0.9fr_0.8fr]">
          <div>
            <p className="text-xs font-semibold tracking-[0.2em] text-ink/50">ABOUT THE PLACE</p>
            <h2 className="mt-3 font-display text-3xl font-semibold text-ink">
              {d?.about_heading ?? "About this place."}
            </h2>
            <p className="mt-4 leading-relaxed text-ink/80">{d?.about_body ?? place.description}</p>
            {d?.experience_note && (
              <p className="mt-8 rotate-[-1deg] font-display text-xl italic text-ink/70">
                {d.experience_note}
              </p>
            )}
          </div>
          <div className="relative overflow-hidden rounded-2xl shadow-lg">
            <PlaceImage slug={place.slug} kind="about" alt={`${place.name} — closer look`} className="h-full min-h-[320px] w-full object-cover" />
            {d?.gallery_caption && (
              <p className="absolute bottom-4 left-4 right-4 font-display text-lg italic text-white drop-shadow">
                {d.gallery_caption}
              </p>
            )}
          </div>
          <aside id="travel-info" className="scroll-mt-24 space-y-4">
            <div className="rounded-2xl bg-white p-6 shadow-md ring-1 ring-ink/5">
              <ul className="space-y-4">
                {infoRows.map(([label, value]) =>
                  value ? (
                    <li key={label} className="text-sm">
                      <p className="font-semibold text-ink">{label}</p>
                      <p className="mt-0.5 text-ink/70">{value}</p>
                    </li>
                  ) : null,
                )}
                {!d?.travel_info && (
                  <li className="text-sm">
                    <p className="font-semibold text-ink">Typical visit</p>
                    <p className="mt-0.5 text-ink/70">
                      {place.typical_visit_minutes ? `~${place.typical_visit_minutes} minutes` : "—"}
                    </p>
                  </li>
                )}
              </ul>
            </div>
            <a
              href={mapsUrl}
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-between rounded-2xl bg-white p-5 shadow-md ring-1 ring-ink/5 transition-shadow hover:shadow-lg"
            >
              <span className="flex items-center gap-3 text-sm font-semibold text-ink">
                <Navigation className="h-4 w-4 text-forest" aria-hidden="true" />
                Open in Maps
              </span>
              <ArrowRight className="h-4 w-4 text-ink/50" aria-hidden="true" />
            </a>
          </aside>
        </div>
      </section>

      {/* ---------- Experiences + Tips ---------- */}
      {(!!d?.experiences?.length || !!d?.travel_tips?.length) && (
        <section id="experiences" className="mx-auto max-w-7xl scroll-mt-24 px-4 pb-12 sm:px-6">
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1.6fr_1fr]">
            {d?.experiences?.length ? (
              <div className="rounded-2xl bg-white p-8 shadow-md ring-1 ring-ink/5">
                <h2 className="font-display text-2xl font-semibold text-ink">What to Experience</h2>
                <ul className="mt-6 grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-5">
                  {d.experiences.slice(0, 9).map((e, i) => {
                    const Icon = EXPERIENCE_ICONS[i % EXPERIENCE_ICONS.length];
                    return (
                      <li key={e.title} className="text-center sm:text-left">
                        <Icon className="mx-auto h-7 w-7 text-ink sm:mx-0" aria-hidden="true" />
                        <p className="mt-3 text-sm font-semibold text-ink">{e.title}</p>
                        <p className="mt-1 text-xs leading-relaxed text-ink/60">{e.description}</p>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ) : null}
            {d?.travel_tips?.length ? (
              <div className="rounded-2xl bg-white p-8 shadow-md ring-1 ring-ink/5">
                <h2 className="font-display text-2xl font-semibold text-ink">
                  Travel Tips &amp; Precautions
                </h2>
                <ul className="mt-6 space-y-3">
                  {d.travel_tips.map((tip) => (
                    <li key={tip} className="flex items-start gap-3 text-sm text-ink/80">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-forest" aria-hidden="true" />
                      {tip}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </section>
      )}

      {/* ---------- Photos ---------- */}
      {d?.gallery?.length ? (
        <section id="photos-videos" className="mx-auto max-w-7xl scroll-mt-24 px-4 pb-12 sm:px-6">
          <div className="flex items-end justify-between">
            <h2 className="font-display text-2xl font-semibold text-ink">Photos &amp; Videos</h2>
            {d.photo_note && (
              <p className="font-display text-lg italic text-ink/60">&ldquo;{d.photo_note}&rdquo;</p>
            )}
          </div>
          <div className="mt-6 flex snap-x gap-4 overflow-x-auto pb-2">
            {d.gallery.map((g, i) => (
              <figure key={g.url} className="w-64 shrink-0 snap-start overflow-hidden rounded-2xl shadow-md">
                <PlaceImage slug={place.slug} kind={`gallery-${i + 1}` as const} alt={g.caption} className="aspect-[16/10] w-full object-cover" />
                <figcaption className="bg-white px-3 py-2 text-xs text-ink/60">{g.caption}</figcaption>
              </figure>
            ))}
          </div>
        </section>
      ) : null}

      {/* ---------- Reviews + Nearby ---------- */}
      <section className="mx-auto max-w-7xl px-4 pb-16 sm:px-6">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
          <div className="rounded-2xl bg-white p-8 shadow-md ring-1 ring-ink/5">
            <ReviewsSection placeSlug={place.slug} />
          </div>

          <div id="nearby" className="scroll-mt-24 rounded-2xl bg-white p-8 shadow-md ring-1 ring-ink/5">
            <h2 className="font-display text-2xl font-semibold text-ink">Nearby Places</h2>
            <p className="mt-1 text-sm text-ink/60">Explore more around {place.city.name}.</p>
            <ul className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
              {(d?.nearby ?? []).map((n) => (
                <li key={n.slug}>
                  <Link href={`/explore/${n.slug}`} className="group block overflow-hidden rounded-xl shadow-sm ring-1 ring-ink/5 transition-shadow hover:shadow-md">
                    <PlaceImage slug={n.slug} kind="hero" alt={n.name} className="aspect-[16/10] w-full object-cover" />
                    <div className="bg-white p-3">
                      <p className="text-sm font-semibold text-ink group-hover:underline">{n.name}</p>
                      {n.label && <p className="text-xs text-ink/50">{n.label}</p>}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
            {!d?.nearby?.length && (
              <p className="mt-4 text-sm text-ink/50">Curated nearby suggestions coming soon.</p>
            )}
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
