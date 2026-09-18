import { Users, Map, ShieldCheck, Leaf, Zap } from "lucide-react";
import { features } from "../../lib/data";

const iconMap = {
  users: Users,
  map: Map,
  shield: ShieldCheck,
  leaf: Leaf,
  zap: Zap,
} as const;

export default function WhyViram() {
  return (
    <section className="mx-auto max-w-7xl px-6 pb-20">
      <h2 className="mb-8 font-display text-3xl font-semibold text-ink md:text-4xl">
        Why Travel with VIR&#256;M?
      </h2>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {features.map((f) => {
          const Icon = iconMap[f.icon];
          return (
            <div
              key={f.title}
              className="rounded-2xl border border-ink/10 bg-white/60 p-6 text-center"
            >
              <Icon className="mx-auto h-8 w-8 text-forest" aria-hidden="true" />
              <h3 className="mt-4 text-sm font-semibold text-ink">{f.title}</h3>
              <p className="mt-2 text-xs leading-relaxed text-ink/65">
                {f.description}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
