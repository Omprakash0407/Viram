import Link from "next/link";
import { notFound } from "next/navigation";
import { MapPin, Phone, Mail, ArrowLeft, BadgeCheck } from "lucide-react";
import { geoApi, providersApi } from "@/lib/api";

export const dynamic = "force-dynamic";

const CATEGORY_LABEL: Record<string, string> = {
  CAFE: "Café",
  RESTAURANT: "Restaurant",
  ARTISAN: "Artisan",
  HANDICRAFT: "Handicraft",
  HOMESTAY: "Homestay",
  FOOD: "Local Food",
  TOUR: "Tour",
  EXPERIENCE: "Experience",
  OTHER: "Local Business",
};

export default async function PartnerDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const business = await providersApi.partner(id).catch(() => null);
  if (!business) notFound();

  const cityList = await geoApi.cities().catch(() => ({ items: [] }));
  const city = cityList.items.find((c) => c.id === business.city_id);

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <Link
        href="/partners"
        className="mb-8 inline-flex items-center gap-2 text-sm font-medium text-ink/70 hover:text-ink"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        All local partners
      </Link>

      <span className="inline-block rounded-full bg-cream-dark px-3 py-1 text-xs font-semibold uppercase tracking-wide text-forest">
        {CATEGORY_LABEL[business.category] ?? business.category}
      </span>
      <h1 className="mt-3 flex items-center gap-3 font-display text-4xl font-semibold text-ink">
        {business.name}
        <BadgeCheck className="h-6 w-6 text-forest" aria-label="Verified by VIRĀM" />
      </h1>
      {business.description ? (
        <p className="mt-4 max-w-2xl text-lg text-ink/75">{business.description}</p>
      ) : null}

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <div className="rounded-2xl bg-white p-6 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-ink/50">Where</h2>
          <p className="mt-2 flex items-center gap-2 text-ink">
            <MapPin className="h-4 w-4 text-forest" aria-hidden="true" />
            {city?.name ?? "Odisha"}, India
          </p>
          {business.public_address ? (
            <p className="mt-1 text-sm text-ink/70">{business.public_address}</p>
          ) : null}
        </div>
        <div className="rounded-2xl bg-white p-6 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-ink/50">Contact</h2>
          {business.public_phone ? (
            <p className="mt-2 flex items-center gap-2 text-ink">
              <Phone className="h-4 w-4 text-forest" aria-hidden="true" />
              {business.public_phone}
            </p>
          ) : null}
          {business.public_email ? (
            <p className="mt-2 flex items-center gap-2 text-ink">
              <Mail className="h-4 w-4 text-forest" aria-hidden="true" />
              {business.public_email}
            </p>
          ) : null}
          {!business.public_phone && !business.public_email ? (
            <p className="mt-2 text-sm text-ink/70">Contact available through VIRĀM bookings.</p>
          ) : null}
        </div>
      </div>

      {business.services.length > 0 ? (
        <div className="mt-4 rounded-2xl bg-white p-6 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-ink/50">What they offer</h2>
          <ul className="mt-3 flex flex-wrap gap-2">
            {business.services.map((s) => (
              <li key={s} className="rounded-full bg-cream px-3 py-1.5 text-sm text-ink">
                {s}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <p className="mt-8 rounded-2xl bg-forest px-6 py-5 text-sm text-cream">
        This partner is verified by the VIRĀM team. Public contact details are shown here; private
        details are only shared through the booking flow.
      </p>
    </main>
  );
}
