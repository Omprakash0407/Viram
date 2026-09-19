import { destinations } from "../../lib/data";
import Link from "next/link";

export default function Destinations() {
  return (
    <section className="mx-auto max-w-7xl px-6 py-16">
      <div className="mb-8 flex items-end justify-between">
        <h2 className="font-display text-3xl font-semibold text-ink md:text-4xl">
          Explore by Destination
        </h2>
        <Link href="/explore"
          className="text-sm font-medium text-ink/70 transition-colors hover:text-ink"
        >
          View All &rarr;
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {destinations.map((d) => (
          <Link
            key={d.name}
            href={`/explore?city=${slugify(d.name)}`}
            className="group relative overflow-hidden rounded-2xl shadow-sm transition-transform duration-200 hover:-translate-y-1"
          >
            <div className="aspect-[3/4] w-full bg-gradient-to-b from-cream-dark to-forest-dark" />
            <div className="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-ink/80 via-ink/20 to-transparent p-4">
              <h3 className="font-display text-lg font-semibold text-white">{d.name}</h3>
              <p className="mt-1 text-xs leading-snug text-white/85">{d.tagline}</p>
            </div>
            <span className="sr-only">Explore {d.name}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}

function slugify(name: string): string {
  return name.toLowerCase().replace(/\s+/g, "-");
}
