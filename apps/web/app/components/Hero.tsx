import { MapPin, Compass, ArrowRight } from "lucide-react";
import Link from "next/link";

interface HeroProps {
  image: string;
}

export default function Hero({ image }: HeroProps) {
  return (
    <section className="relative min-h-[520px] overflow-hidden">
      {/* Background image with warm overlay for text legibility */}
      <div
        className="absolute inset-0 bg-cover bg-center"
        style={{ backgroundImage: `url(${image})` }}
        aria-hidden="true"
      />
      <div
        className="absolute inset-0 bg-gradient-to-r from-ink/80 via-ink/40 to-transparent"
        aria-hidden="true"
      />

      <div className="relative mx-auto flex max-w-7xl flex-col justify-center px-6 py-24 md:py-32">
        <h1 className="font-display text-5xl font-semibold tracking-tight text-white md:text-7xl">
          Pause. Explore. Belong.
        </h1>
        <p className="mt-5 max-w-xl text-lg text-white/90">
          Discover India&apos;s soul through its places, people and culture.
          <br className="hidden md:block" /> Your intelligent travel companion.
        </p>

        {/* Search bar */}
        <form
          className="mt-8 flex max-w-xl items-center gap-2 rounded-full bg-white p-2 pl-5 shadow-lg"
          action="/plan"
        >
          <MapPin className="h-5 w-5 shrink-0 text-forest" aria-hidden="true" />
          <input
            type="text"
            name="q"
            placeholder="Where do you want to explore?"
            className="w-full bg-transparent text-ink outline-none placeholder:text-ink/50"
            aria-label="Where do you want to explore?"
          />
          <button
            type="submit"
            className="flex shrink-0 items-center gap-2 rounded-full bg-forest px-6 py-3 font-medium text-white transition-colors hover:bg-forest-dark"
          >
            Search <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </form>

        {/* Explore CTA */}
        <div className="mt-6">
          <Link href="/explore"
            className="inline-flex items-center gap-2 rounded-full bg-forest px-7 py-4 font-medium text-white transition-colors hover:bg-forest-dark"
          >
            <Compass className="h-5 w-5" aria-hidden="true" />
            Explore
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </div>
      </div>

      {/* Handwritten-style accent note */}
      <div className="absolute right-10 top-16 hidden -rotate-6 text-right font-display text-2xl italic text-white lg:block">
        More
        <br />
        Than Travel,
        <br />A Deeper Connection
      </div>

      {/* Location caption */}
      <div className="absolute bottom-5 right-6 flex items-center gap-1.5 text-sm text-white/90">
        <MapPin className="h-4 w-4" aria-hidden="true" />
        Rishikesh, Uttarakhand
      </div>
    </section>
  );
}
