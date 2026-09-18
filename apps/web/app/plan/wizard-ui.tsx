"use client";

import Image from "next/image";
import Link from "next/link";

export function Stepper({ current }: { current: 1 | 2 | 3 }) {
  const steps = [
    { n: 1 as const, title: "Tell Us Your Preferences", sub: "Share your travel style, budget and what you love." },
    { n: 2 as const, title: "Get Your Plan", sub: "We'll create a personalized itinerary just for you." },
    { n: 3 as const, title: "Review & Customize", sub: "Fine-tune, add or remove experiences. You're in control." },
  ];
  return (
    <ol className="flex items-start justify-between gap-2">
      {steps.map(({ n, title, sub }, idx) => {
        const state = n < current ? "done" : n === current ? "active" : "todo";
        return (
          <li key={n} className="relative flex flex-1 flex-col items-center text-center">
            {idx > 0 && (
              <span
                aria-hidden="true"
                className={`absolute top-[18px] right-1/2 h-px w-full ${n <= current ? "bg-forest" : "bg-ink/20"}`}
              />
            )}
            <span
              className={`relative z-10 flex h-9 w-9 items-center justify-center rounded-full text-sm font-semibold ${
                state === "todo" ? "bg-ink/10 text-ink/60" : "bg-forest text-white"
              }`}
            >
              {n}
            </span>
            <span className={`relative z-10 mt-2 text-sm font-semibold ${state === "todo" ? "text-ink/50" : "text-ink"}`}>
              {title}
            </span>
            <span className="relative z-10 hidden text-xs text-ink/50 md:block">{sub}</span>
          </li>
        );
      })}
    </ol>
  );
}

/** Step-2 header stepper: Preferences / Itinerary / Booking in mock style. */
export function DayStepper({ current }: { current: 2 | 3 }) {
  const steps = ["Preferences", "The Generated Itinerary", "Hotels, Flights & Local Activities Booking"];
  return (
    <ol className="flex items-start justify-between gap-2">
      {steps.map((label, i) => {
        const n = i + 1;
        const state = n < current ? "done" : n === current ? "active" : "todo";
        return (
          <li key={label} className="relative flex flex-1 flex-col items-center text-center">
            {i > 0 && (
              <span
                aria-hidden="true"
                className={`absolute top-[18px] right-1/2 h-px w-full ${n <= current ? "bg-forest" : "bg-ink/20"}`}
              />
            )}
            <span
              className={`relative z-10 flex h-9 w-9 items-center justify-center rounded-full text-sm font-semibold ${
                state === "done" ? "bg-forest text-white" : state === "active" ? "bg-forest text-white" : "bg-ink/10 text-ink/60"
              }`}
            >
              {n}
            </span>
            <span className={`relative z-10 mt-2 max-w-[16ch] text-xs font-semibold leading-snug ${state === "todo" ? "text-ink/50" : "text-ink"}`}>
              {label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * Full-height Plan-a-Trip page frame: full-bleed scenic background photo
 * (temple shoreline at sunset, word-free) with the wizard card centred on top.
 */
export function PlanShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative w-full">
      {/* Fixed full-bleed background — behind everything, scrolls with content */}
      <div aria-hidden="true" className="fixed inset-0 -z-10">
        <Image
          src="/images/plan-bg.jpg"
          alt=""
          fill
          priority
          sizes="100vw"
          className="hidden object-cover md:block"
        />
        <Image
          src="/images/plan-bg-mobile.jpg"
          alt=""
          fill
          priority
          sizes="100vw"
          className="object-cover md:hidden"
        />
        {/* Soft vignette so the card edges read cleanly */}
        <div className="absolute inset-0 bg-black/10" />
      </div>

      {/* Centred wizard card */}
      <section className="mx-auto w-full max-w-[960px] px-3 py-6 sm:px-6 sm:py-10">
        <div className="rounded-2xl bg-cream/95 shadow-2xl ring-1 ring-ink/10 backdrop-blur-sm">
          {children}
        </div>
      </section>
    </div>
  );
}

/** Primary full-width deep-green CTA used across wizard steps. */
export function PrimaryButton({
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={`w-full rounded-xl bg-forest px-6 py-4 text-base font-semibold text-white transition-colors hover:bg-forest-dark disabled:cursor-not-allowed disabled:opacity-60 ${props.className ?? ""}`}
    >
      {children}
    </button>
  );
}

export function SecondaryButton({
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={`w-full rounded-xl border border-ink/20 bg-transparent px-6 py-4 text-base font-semibold text-ink transition-colors hover:bg-ink/5 disabled:opacity-60 ${props.className ?? ""}`}
    >
      {children}
    </button>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
      {message}
    </p>
  );
}

/** Small helper so step headers can link back home like the mock nav. */
export function HomeLink() {
  return (
    <Link href="/" className="text-xs font-medium text-ink/60 underline-offset-4 hover:underline">
      Home
    </Link>
  );
}
