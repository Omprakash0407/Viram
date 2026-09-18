"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CalendarDays,
  ChevronDown,
  Clock,
  Heart,
  Loader2,
  MapPin,
  Search,
  Wallet,
} from "lucide-react";
import {
  geoApi,
  planningApi,
  usersApi,
  type BudgetRow,
  type CityRow,
  type MoodRow,
  type TripCreatePayload,
} from "@/lib/api";
import { ErrorNote, PrimaryButton } from "./wizard-ui";

export const INTEREST_OPTIONS = [
  "Mountains",
  "Beaches",
  "Temples",
  "Wildlife",
  "Waterfalls",
  "Food",
  "Nightlife",
  "Heritage",
  "Shopping",
] as const;

const DURATION_BANDS = [
  { label: "3–5 days", min: 3, max: 5 },
  { label: "6–8 days", min: 6, max: 8 },
  { label: "9–12 days", min: 9, max: 12 },
  { label: "13+ days", min: 13, max: 21 },
];

const MOOD_ICONS: Record<string, string> = {
  NATURE_RELAXATION: "🌿",
  CITY_LIFE: "🏙️",
  ADVENTURE_THRILL: "🥾",
  FOOD_CULTURE: "🍽️",
};

function todayPlus(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function nightsLabel(starts: string, ends: string): string {
  if (!starts || !ends) return "";
  const s = new Date(starts);
  const e = new Date(ends);
  const days = Math.round((e.getTime() - s.getTime()) / 86_400_000) + 1;
  return days > 0 ? `${days} day${days === 1 ? "" : "s"}` : "";
}

export function Step1Preferences({
  onSubmit,
  busy,
  error,
}: {
  onSubmit: (payload: TripCreatePayload, interests: string[]) => void;
  busy: boolean;
  error: string | null;
}) {
  const [cities, setCities] = useState<CityRow[]>([]);
  const [moods, setMoods] = useState<MoodRow[]>([]);
  const [budgetTiers, setBudgetTiers] = useState<BudgetRow[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [cityQuery, setCityQuery] = useState("");
  const [cityOpen, setCityOpen] = useState(false);
  const [city, setCity] = useState<CityRow | null>(null);
  const [startsOn, setStartsOn] = useState(todayPlus(14));
  const [endsOn, setEndsOn] = useState(todayPlus(16));
  const [band, setBand] = useState<number | null>(0);
  const [budget, setBudget] = useState<string>("MODERATE");
  const [pickedMoods, setPickedMoods] = useState<string[]>([]);
  const [interests, setInterests] = useState<string[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const [c, m, b] = await Promise.all([
          geoApi.cities(),
          planningApi.moods(),
          planningApi.budgetTiers(),
        ]);
        setCities(c.items);
        setMoods(m.items);
        setBudgetTiers(b.items);
      } catch {
        setLoadError("Could not load destinations. Is the API running?");
      }
    })();
  }, []);

  // Pre-check interests the traveller saved previously (profile preferences).
  useEffect(() => {
    (async () => {
      try {
        const prefs = await usersApi.getPreferences();
        const saved = (prefs.interests ?? []).map((i) =>
          i.charAt(0).toUpperCase() + i.slice(1).toLowerCase(),
        );
        const valid = saved.filter((s) => (INTEREST_OPTIONS as readonly string[]).includes(s));
        if (valid.length) setInterests(valid);
      } catch {
        // optional — ignore
      }
    })();
  }, []);

  const filteredCities = useMemo(() => {
    const q = cityQuery.trim().toLowerCase();
    if (!q) return cities.slice(0, 8);
    return cities.filter((c) => c.name.toLowerCase().includes(q)).slice(0, 8);
  }, [cities, cityQuery]);

  function toggle<T>(list: T[], item: T): T[] {
    return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
  }

  function pickCity(c: CityRow) {
    setCity(c);
    setCityQuery(c.name);
    setCityOpen(false);
  }

  function pickBand(i: number) {
    setBand(i);
    const b = DURATION_BANDS[i];
    setStartsOn(todayPlus(14));
    setEndsOn(todayPlus(14 + b.min - 1));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!city) return;
    onSubmit(
      {
        city_id: city.id,
        starts_on: startsOn,
        ends_on: endsOn,
        party_size: 1,
        moods: pickedMoods.length ? pickedMoods : [moods[0]?.key ?? "NATURE_RELAXATION"],
        budget_tier: budget,
      },
      interests,
    );
  }

  const daysLabel = nightsLabel(startsOn, endsOn);

  return (
    <form onSubmit={submit} className="space-y-6">
      <div>
        <h1 className="font-display text-4xl font-semibold text-ink">Let&rsquo;s plan your trip</h1>
        <p className="mt-2 text-sm text-ink/60">
          Share a few details to get started. You can always customize them later.
        </p>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        {/* Where */}
        <div className="rounded-xl bg-white/60 p-5 ring-1 ring-ink/10">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
            <MapPin className="h-4 w-4" aria-hidden="true" /> Where do you want to go?
          </div>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink/40" aria-hidden="true" />
            <input
              value={cityQuery}
              onChange={(e) => {
                setCityQuery(e.target.value);
                setCityOpen(true);
                setCity(null);
              }}
              onFocus={() => setCityOpen(true)}
              placeholder="Search destinations (e.g. Puri, Bhubaneswar…)"
              aria-label="Search destinations"
              className="w-full rounded-lg border border-ink/15 bg-white py-2.5 pl-9 pr-3 text-sm outline-none focus:border-forest"
            />
            {cityOpen && filteredCities.length > 0 && (
              <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-lg bg-white py-1 shadow-lg ring-1 ring-ink/10">
                {filteredCities.map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => pickCity(c)}
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-cream"
                    >
                      <MapPin className="h-3.5 w-3.5 text-ink/40" aria-hidden="true" />
                      {c.name}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* When */}
        <div className="rounded-xl bg-white/60 p-5 ring-1 ring-ink/10">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
            <CalendarDays className="h-4 w-4" aria-hidden="true" /> When are you travelling?
          </div>
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={startsOn}
              onChange={(e) => setStartsOn(e.target.value)}
              aria-label="Start date"
              className="w-full rounded-lg border border-ink/15 bg-white px-3 py-2.5 text-sm outline-none focus:border-forest"
            />
            <span className="text-ink/40">→</span>
            <input
              type="date"
              value={endsOn}
              min={startsOn}
              onChange={(e) => setEndsOn(e.target.value)}
              aria-label="End date"
              className="w-full rounded-lg border border-ink/15 bg-white px-3 py-2.5 text-sm outline-none focus:border-forest"
            />
          </div>
          {daysLabel && <p className="mt-2 text-xs text-ink/50">{daysLabel}</p>}
        </div>

        {/* Duration */}
        <div className="rounded-xl bg-white/60 p-5 ring-1 ring-ink/10">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
            <Clock className="h-4 w-4" aria-hidden="true" /> Trip Duration
          </div>
          <div className="flex flex-wrap gap-2">
            {DURATION_BANDS.map((b, i) => (
              <button
                key={b.label}
                type="button"
                aria-pressed={band === i}
                onClick={() => pickBand(i)}
                className={`rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
                  band === i ? "bg-forest text-white" : "bg-white text-ink ring-1 ring-ink/15 hover:bg-cream-dark"
                }`}
              >
                {b.label}
              </button>
            ))}
          </div>
        </div>

        {/* Budget */}
        <div className="rounded-xl bg-white/60 p-5 ring-1 ring-ink/10">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
            <Wallet className="h-4 w-4" aria-hidden="true" /> Your Budget (per person)
          </div>
          <div className="flex flex-wrap gap-2">
            {budgetTiers.map((t) => (
              <button
                key={t.key}
                type="button"
                title={t.label}
                aria-pressed={budget === t.key}
                onClick={() => setBudget(t.key)}
                className={`rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
                  budget === t.key ? "bg-forest text-white" : "bg-white text-ink ring-1 ring-ink/15 hover:bg-cream-dark"
                }`}
              >
                {t.key.charAt(0) + t.key.slice(1).toLowerCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Moods */}
      <div className="rounded-xl bg-white/60 p-5 ring-1 ring-ink/10">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
          <Heart className="h-4 w-4" aria-hidden="true" /> Your Travel Style / Mood
        </div>
        <div className="flex flex-wrap gap-2">
          {moods.map((m) => (
            <button
              key={m.key}
              type="button"
              aria-pressed={pickedMoods.includes(m.key)}
              onClick={() => setPickedMoods(toggle(pickedMoods, m.key))}
              className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
                pickedMoods.includes(m.key) ? "bg-forest text-white" : "bg-white text-ink ring-1 ring-ink/15 hover:bg-cream-dark"
              }`}
            >
              <span aria-hidden="true">{MOOD_ICONS[m.key] ?? "✦"}</span>
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Interests */}
      <div className="rounded-xl bg-white/60 p-5 ring-1 ring-ink/10">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
          <ChevronDown className="h-4 w-4" aria-hidden="true" /> What interests you?
        </div>
        <div className="flex flex-wrap gap-2">
          {INTEREST_OPTIONS.map((opt) => (
            <button
              key={opt}
              type="button"
              aria-pressed={interests.includes(opt)}
              onClick={() => setInterests(toggle(interests, opt))}
              className={`rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
                interests.includes(opt) ? "bg-forest text-white" : "bg-white text-ink ring-1 ring-ink/15 hover:bg-cream-dark"
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
        <p className="mt-3 text-xs text-ink/50">
          Saved to your profile so future plans start from what you love.
        </p>
      </div>

      <ErrorNote message={loadError ?? error} />

      <PrimaryButton type="submit" disabled={busy || !city}>
        {busy ? (
          <span className="inline-flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Building your plan…
          </span>
        ) : (
          "Next →"
        )}
      </PrimaryButton>
    </form>
  );
}
