"use client";

import { useState } from "react";
import Link from "next/link";
import Header from "@/app/components/Header";
import Footer from "@/app/components/Footer";
import { tripsApi, usersApi, type TripCreatePayload, type TripDetail } from "@/lib/api";
import type { RecommendationUI } from "./types";
import { AuthGate } from "@/app/components/AuthPanel";
import { PlanShell, Stepper } from "./wizard-ui";
import { Step1Preferences } from "./Step1Preferences";
import { Step2Itinerary } from "./Step2Itinerary";
import { Step3Bookings } from "./Step3Bookings";

type Step = 1 | 2 | 3;

export default function PlanTripPage() {
  const [step, setStep] = useState<Step>(1);
  const [trip, setTrip] = useState<TripDetail | null>(null);
  const [recs, setRecs] = useState<RecommendationUI[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handlePreferencesSubmit(payload: TripCreatePayload, interests: string[]) {
    setError(null);
    setBusy(true);
    try {
      // Persist interests to the traveller profile (step 1 → profile), then
      // create the trip with the reproducible preference snapshot.
      if (interests.length) {
        await usersApi.updatePreferences({
          interests: interests.map((i) => i.toLowerCase()),
        });
      }
      const created = await tripsApi.create(payload);
      const rec = await tripsApi.recommendations(created.id, true);
      setRunId(rec.run_id);
      setRecs(rec.items);
      const detail = await tripsApi.detail(created.id);
      setTrip(detail);
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the trip.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1">
        <AuthGate>
          <PlanShell>
            <div className="space-y-8 px-5 py-6 sm:px-8 sm:py-8">
              <Stepper current={step} />

              {step === 1 && (
                <Step1Preferences onSubmit={handlePreferencesSubmit} busy={busy} error={error} />
              )}

              {step === 2 && trip && (
                <Step2Itinerary
                  trip={trip}
                  recommendations={recs}
                  runId={runId}
                  onProceedToBookings={() => setStep(3)}
                  onTripUpdated={setTrip}
                />
              )}

              {step === 3 && trip && <Step3Bookings trip={trip} onBack={() => setStep(2)} />}

              <p className="text-center text-xs text-ink/40">
                Prefer browsing first?{" "}
                <Link href="/" className="underline underline-offset-4">
                  Return home
                </Link>
              </p>
            </div>
          </PlanShell>
        </AuthGate>
      </main>
      <Footer />
    </div>
  );
}
