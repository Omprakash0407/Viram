import Link from "next/link";
import { MapPin, Sparkles } from "lucide-react";
import Header from "@/app/components/Header";
import Footer from "@/app/components/Footer";
import { INDIA_STATES } from "./states";

/** States with seeded, editorially verified content (everything else 404s). */
const LIVE_STATES = new Set(["odisha"]);

export default function ExplorePage() {
  return (
    <div className="bg-cream">
      <Header />
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
        <header className="mb-10">
          <p className="text-xs font-semibold tracking-[0.2em] text-ink/50">EXPLORE INDIA</p>
          <h1 className="mt-2 font-display text-4xl font-semibold text-ink sm:text-5xl">
            Every state has a story worth pausing for.
          </h1>
          <p className="mt-3 max-w-2xl text-ink/70">
            Pick a state to browse its cities and places. VIRĀM grows state by state — each one
            opens only after its destinations are verified with local communities, never invented.
          </p>
        </header>

        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {INDIA_STATES.map((s) => {
            const live = LIVE_STATES.has(s.slug);
            const card = (
              <>
                <div className="flex items-start justify-between gap-2">
                  <h2 className="font-display text-lg font-semibold text-ink">{s.name}</h2>
                  {live ? (
                    <span className="rounded-full bg-forest px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-white">
                      Explore
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 rounded-full bg-ink/5 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-ink/45">
                      <Sparkles className="h-3 w-3" aria-hidden="true" />
                      Coming soon
                    </span>
                  )}
                </div>
                <p className="mt-2 flex items-center gap-1.5 text-sm text-ink/55">
                  <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
                  {live ? "Cities & places ready" : "Verified content on the way"}
                </p>
              </>
            );

            return (
              <li key={s.slug}>
                {live ? (
                  <Link
                    href={`/explore/state/${s.slug}`}
                    className="block h-full rounded-2xl bg-white p-5 shadow-md ring-1 ring-ink/5 transition-shadow hover:shadow-xl"
                  >
                    {card}
                  </Link>
                ) : (
                  <div
                    aria-disabled="true"
                    title="Content for this state is being verified"
                    className="h-full cursor-not-allowed rounded-2xl bg-white/60 p-5 shadow-sm ring-1 ring-ink/5"
                  >
                    {card}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </div>
      <Footer />
    </div>
  );
}
