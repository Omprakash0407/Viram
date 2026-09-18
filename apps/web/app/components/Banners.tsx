import { ArrowRight } from "lucide-react";
import Link from "next/link";

export default function Banners() {
  return (
    <section className="mx-auto grid max-w-7xl gap-4 px-6 pb-16 md:grid-cols-2">
      {/* Culture banner */}
      <div className="relative overflow-hidden rounded-3xl bg-forest-dark p-8 text-white md:p-10">
        <div
          className="absolute inset-0 bg-cover bg-center opacity-40"
          style={{ backgroundImage: "url(/images/culture.svg)" }}
          aria-hidden="true"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-forest-dark/95 via-forest-dark/70 to-transparent" aria-hidden="true" />
        <div className="relative max-w-sm">
          <h2 className="font-display text-3xl font-semibold leading-tight">
            Experience the Real India
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-white/85">
            Traditions, festivals, food, crafts and stories from the heart of
            every destination.
          </p>
          <Link href="/culture"
            className="mt-6 inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-medium text-forest transition-colors hover:bg-cream"
          >
            Explore Culture <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </div>
      </div>

      {/* Plan smarter banner */}
      <div className="relative overflow-hidden rounded-3xl bg-cream-dark p-8 md:p-10">
        <div className="relative max-w-sm">
          <h2 className="font-display text-3xl font-semibold leading-tight text-ink">
            Plan Smarter
            <br />
            Travel Better
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-ink/75">
            Get personalized itineraries, routes, weather updates and local
            recommendations.
          </p>
          <Link href="/plan"
            className="mt-6 inline-flex items-center gap-2 rounded-full bg-forest px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-forest-dark"
          >
            Plan Your Trip <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </div>
        {/* Decorative route dots */}
        <svg
          className="absolute right-0 top-0 hidden h-full w-1/2 text-forest/70 md:block"
          viewBox="0 0 300 260"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M20 200 C 80 120, 140 220, 190 140 S 270 60, 290 40"
            stroke="currentColor"
            strokeWidth="2"
            strokeDasharray="6 6"
          />
          {[
            { x: 20, y: 200, label: "Places" },
            { x: 120, y: 165, label: "Food" },
            { x: 190, y: 140, label: "Stays" },
            { x: 260, y: 80, label: "Guides" },
          ].map((p) => (
            <g key={p.label}>
              <circle cx={p.x} cy={p.y} r="7" fill="#1e3a2f" />
              <circle cx={p.x} cy={p.y} r="3" fill="#f4f0e8" />
              <text x={p.x + 12} y={p.y + 4} fontSize="13" fill="#1d2620">
                {p.label}
              </text>
            </g>
          ))}
        </svg>
      </div>
    </section>
  );
}
