"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Loader2, Star, Trash2 } from "lucide-react";
import { reviewsApi, type ReviewRow } from "@/lib/api";
import { useSession } from "@/lib/session";

function Stars({ value, size = "h-4 w-4" }: { value: number; size?: string }) {
  return (
    <span className="inline-flex items-center gap-0.5" aria-label={`${value} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <Star
          key={n}
          className={`${size} ${n <= value ? "fill-amber-500 text-amber-500" : "text-ink/25"}`}
          aria-hidden="true"
        />
      ))}
    </span>
  );
}

/**
 * Real traveller reviews for one place (design §24): public list + live
 * aggregate, auth-gated submission (one per author per place), delete-own.
 * Replaces the sample-review layout preview.
 */
export default function ReviewsSection({ placeSlug }: { placeSlug: string }) {
  const { user } = useSession();
  const [reviews, setReviews] = useState<ReviewRow[] | null>(null);
  const [avg, setAvg] = useState<number | null>(null);
  const [count, setCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [rating, setRating] = useState(5);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [visitedOn, setVisitedOn] = useState("");

  const myReviewId = useMemo(
    () => reviews?.find((r) => r.author.display_name === user?.display_name)?.id ?? null,
    [reviews, user],
  );

  async function refresh() {
    try {
      const r = await reviewsApi.list(placeSlug);
      setReviews(r.items);
      setAvg(r.rating_avg);
      setCount(r.review_count);
    } catch {
      setError("Could not load reviews.");
    }
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once per slug
  }, [placeSlug]);

  async function submit() {
    setError(null);
    setBusy(true);
    try {
      const r = await reviewsApi.create(placeSlug, {
        rating,
        title: title.trim() || undefined,
        body: body.trim(),
        visited_on: visitedOn.trim() || undefined,
      });
      setAvg(r.rating_avg);
      setCount(r.review_count);
      setReviews((prev) => [r.review, ...(prev ?? [])]);
      setTitle("");
      setBody("");
      setVisitedOn("");
      setRating(5);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not submit the review.";
      setError(/already/i.test(msg) ? "You have already reviewed this place." : msg);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setError(null);
    try {
      await reviewsApi.remove(id);
      setReviews((prev) => (prev ?? []).filter((r) => r.id !== id));
      await refresh(); // aggregates changed
    } catch {
      setError("Could not delete the review.");
    }
  }

  return (
    <section id="reviews" className="scroll-mt-24">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-display text-2xl font-semibold text-ink">Traveller Reviews</h2>
        <p className="text-sm text-ink/60">
          {avg != null ? (
            <>
              <span className="font-semibold text-ink">{avg.toFixed(1)} / 5</span> · {count} review
              {count === 1 ? "" : "s"}
            </>
          ) : (
            "No reviews yet"
          )}
        </p>
      </div>

      {error && <p className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      {/* Write form (auth-gated) */}
      {user ? (
        myReviewId ? (
          <p className="mt-4 rounded-xl bg-forest/5 p-4 text-sm text-ink/70 ring-1 ring-forest/10">
            You have already shared your experience here — thank you.
          </p>
        ) : (
          <div className="mt-4 rounded-xl bg-white p-5 ring-1 ring-ink/10">
            <p className="text-sm font-semibold text-ink">Share your experience</p>
            <div className="mt-3 flex items-center gap-1.5">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setRating(n)}
                  aria-label={`Rate ${n} star${n > 1 ? "s" : ""}`}
                  className="p-0.5"
                >
                  <Star
                    className={`h-6 w-6 transition-colors ${
                      n <= rating ? "fill-amber-500 text-amber-500" : "text-ink/25 hover:text-amber-400"
                    }`}
                    aria-hidden="true"
                  />
                </button>
              ))}
            </div>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Title (optional)"
              maxLength={140}
              className="mt-3 w-full rounded-lg border border-ink/15 px-3 py-2 text-sm outline-none focus:border-forest"
            />
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="What made this place worth the pause? (min 10 characters)"
              rows={3}
              maxLength={4000}
              className="mt-2 w-full rounded-lg border border-ink/15 px-3 py-2 text-sm outline-none focus:border-forest"
            />
            <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
              <input
                value={visitedOn}
                onChange={(e) => setVisitedOn(e.target.value)}
                placeholder="When did you visit? (e.g. Dec 2025)"
                maxLength={20}
                className="w-56 rounded-lg border border-ink/15 px-3 py-2 text-sm outline-none focus:border-forest"
              />
              <button
                type="button"
                onClick={() => void submit()}
                disabled={busy || body.trim().length < 10}
                className="inline-flex items-center gap-2 rounded-full bg-forest px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-forest-dark disabled:opacity-50"
              >
                {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
                Post review
              </button>
            </div>
          </div>
        )
      ) : (
        <p className="mt-4 rounded-xl bg-cream-dark/60 p-4 text-sm text-ink/70">
          <Link href="/login" className="font-semibold text-forest underline">
            Sign in
          </Link>{" "}
          to share your own review of this place.
        </p>
      )}

      {/* List */}
      {reviews === null ? (
        <p className="mt-6 flex items-center gap-2 text-sm text-ink/50">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Loading reviews…
        </p>
      ) : reviews.length === 0 ? (
        <p className="mt-6 text-sm text-ink/50">
          No traveller reviews yet — be the first to share yours.
        </p>
      ) : (
        <ul className="mt-6 space-y-4">
          {reviews.map((r) => (
            <li key={r.id} className="rounded-xl bg-white p-5 ring-1 ring-ink/10">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-ink">{r.author.display_name}</p>
                  <p className="mt-0.5 flex items-center gap-2 text-xs text-ink/50">
                    <Stars value={r.rating} />
                    {r.visited_on && <span>· Visited {r.visited_on}</span>}
                    <span>· {new Date(r.created_at).toLocaleDateString("en-IN")}</span>
                  </p>
                </div>
                {user?.display_name === r.author.display_name && (
                  <button
                    type="button"
                    onClick={() => void remove(r.id)}
                    aria-label="Delete my review"
                    className="rounded-md p-2 text-ink/40 transition-colors hover:bg-red-50 hover:text-red-600"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                )}
              </div>
              {r.title && <p className="mt-2 text-sm font-semibold text-ink">{r.title}</p>}
              <p className="mt-1 text-sm leading-relaxed text-ink/75">{r.body}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
