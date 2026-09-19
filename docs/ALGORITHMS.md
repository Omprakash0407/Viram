# VIRĀM — Algorithms & Technical Logic

**Status:** documents the implemented codebase (SIH 2026 demo).
**Sources of truth:** the files referenced in each section. If this doc and the code disagree, the code wins.

Sections 1–4 are the intelligence layer (recommendations, itineraries). Sections 5–13 cover
security and commerce correctness. Sections 14–17 cover supporting logic. Each section gives:
the **algorithm**, the **formula/constants**, **why it was designed this way**, and the exact
**file reference**.

---

## 1. Rule-Based Recommendation Scoring (rules-v1)

**File:** `apps/api/app/modules/planning/engine.py` — `RuleBasedRecommendationEngine._score()`
**Engine identity:** `engine_name = "RuleBasedRecommendationEngine"`, `engine_version = "rules-v1"`

### Formula

```
score = 3.0 · category_match
      + 2.0 · rating
      + 1.5 · popularity
      + 0.15 · lesser_known_bonus
```

| Term | Value | Default when data missing |
|---|---|---|
| `category_match` | `1.0` — the candidate query already filtered places to mood-matched categories, so every candidate matches | — |
| `rating` | editorial `rating_avg` (0–5 scale) | **3.0** (neutral mid-rating) |
| `popularity` | `popularity_score / 100` (0–1) | **0.5** (neutral) |
| `lesser_known_bonus` | `0.15` if `classification == "LESSER_KNOWN"` else `0.0` | — |

Scores are quantized to 2 decimals: `Decimal(str(raw)).quantize(Decimal("0.01"))`.

### Candidate selection

```sql
SELECT place FROM places
JOIN place_categories ON places.category_id = place_categories.id
WHERE places.city_id = :trip_city
  AND places.status = 'ACTIVE'
  AND place_categories.slug IN (:mood_category_slugs)
LIMIT 200
```

The mood → category mapping lives in
`apps/api/app/modules/planning/schemas.py` (`MOOD_CATEGORIES`) — **data-driven, not hardcoded
in the engine**:

```
NATURE_RELAXATION  → nature, scenic, lakes, wildlife, parks
CITY_LIFE          → city-life, markets, museums, fun
ADVENTURE_THRILL   → adventure, trekking, wildlife
FOOD_CULTURE       → heritage, food, culture, crafts
```

### Ranking

Candidates are sorted by `(-score, name)` — score descending, **place name ascending as the
tie-break**. This makes the engine fully **deterministic**: identical inputs always produce an
identical ranking, which is a hard requirement for reproducible recommendation runs (§4).

### Why this design

- The weights (3 : 2 : 1.5) say: *interest match dominates*, then *quality*, then *popularity
  as a soft signal only* — so the engine does not simply echo famous places (project rule:
  lesser-known places must get real visibility).
- Deterministic + explainable is the SIH-appropriate MVP: every score can be defended in a
  demo, and a future `AIRecommendationEngine` can implement the same `EngineResult` interface
  (`engine_name`, `engine_version`, `preference_snapshot`, `items`) with **zero schema
  changes** — the replaceability contract of design doc §13.

### Worked example

Place with `rating_avg = 4.6`, `popularity_score = 70`, `LESSER_KNOWN`:

```
score = 3.0·1.0 + 2.0·4.6 + 1.5·0.70 + 0.15 = 3.0 + 9.2 + 1.05 + 0.15 = 13.40
```

---

## 2. Hidden-Gem Interleave (lesser-known share guarantee)

**File:** `apps/api/app/modules/planning/engine.py` — `_to_items()`

A plain score sort would bury hidden gems (they usually lack ratings/history). Instead the
ranked output is **interleaved**:

```
LESSER_KNOWN_TARGET_SHARE = 0.25      # at least 25% of output, min 1 gem
target_lesser = int(len(scored) * 0.25)
```

Loop, until both pools are exhausted:

1. Pop up to **3 places from the popular pool** (already score-sorted).
2. If the gems delivered so far are below `max(target_lesser, 1)` **or** the popular pool is
   empty, pop **1 place from the lesser-known pool**.

Every branch consumes from a pool, so the loop always terminates.

**Guarantee:** a plan for a city with ≥ 4 candidates always contains hidden gems, at roughly
a **3 popular : 1 gem rhythm** near the top of the list.

Each output item also gets a **human-readable explanation**:

- lesser-known → `"Hidden gem: {lesser_known_note or 'a local hidden gem'}"`
- popular → `"Matches your interests; {rating} rating; popularity {n}/100"` (parts omitted
  when the data is null)

This satisfies design doc §13 ("explanation" as a first-class output) and makes the UI
self-documenting.

---

## 3. Itinerary Distribution (balanced day-split)

**Files:** `apps/api/app/modules/planning/service.py` — `generate_itinerary()`

Given `n` accepted recommendation items (sorted by engine rank) and `d` trip days:

```
per_day = ceil(n / d)                      # balanced fill
day(i)  = min(i // per_day, d − 1)         # i = 0-based item index
position(i) = (i mod per_day) × 10         # DAY_START_POSITION_STEP = 10
```

Properties:

- **One `ItineraryDay` row per trip date** (`starts_on + timedelta(days=k)`, `k = 0..d−1`) —
  the day grid is derived from real dates, not a counter.
- **One active itinerary per trip** — a second generation attempt raises `409 Conflict`
  (`ConflictError`); afterwards the itinerary is *customized*, never regenerated.
- **Position slots are spaced by 10** (`DAY_START_POSITION_STEP = 10`): inserting an item
  between position 20 and 30 can take position 25 **without renumbering siblings** — the
  classic sparse-ordering trick (same idea as BASIC line numbers / LexoRank-lite).
- **Provenance is preserved:** every `ItineraryItem` stores its source
  `recommendation_item_id`, so the dashboard can always explain *why* a place is on day 2.

Example — 7 accepted items over 3 days: `per_day = 3` → day 1 gets items 1–3, day 2 items
4–6, day 3 item 7.

---

## 4. Preference Snapshot & Hybrid Recommendation Persistence

**Files:** `apps/api/app/modules/planning/service.py` — `create_trip()`, `generate_recommendations()`

- Trip creation freezes the planning context into `preferences_snapshot`:
  `{"moods": [...], "budget_tier": "...", "party_size": n, "days": d}`.
- Recommendation runs are **hybrid persistent** (design doc §13): casual browsing is transient
  (`persist = false` → nothing written); saved/accepted runs write a `RecommendationRun` +
  ranked `RecommendationItem` rows carrying `engine_name`, `engine_version`,
  `preference_snapshot`, `score`, `rank`, `explanation`, `accepted`.
- Because the snapshot + engine version are stored, any past run can be **reproduced or
  audited** even after the user changes preferences or the engine is upgraded to an AI model.

---

## 5. Password Hashing — Argon2id

**File:** `apps/api/app/core/security.py`

```python
_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
```

- **Argon2id** is the memory-hard KDF recommended by OWASP; it resists GPU/ASIC cracking
  far better than bcrypt/PBKDF2. `deprecated="auto"` lets the scheme be upgraded later
  without breaking existing logins (old hashes re-hash transparently on next login).
- Raw passwords are never logged or stored; only the Argon2 hash persists.

---

## 6. JWT Access Tokens + Hashed Refresh Tokens

**File:** `apps/api/app/core/security.py`

- Access tokens: **HS256** JWTs signed with the server-side `JWT_SECRET_KEY`.
- Refresh tokens: stored **only as a SHA-256 hash** —
  `hash_refresh_token(raw) = sha256(raw.encode()).hexdigest()`.
- Verification uses **constant-time comparison**:
  `hmac.compare_digest(hash_refresh_token(raw), stored_hash)`.

Why: a DB leak then exposes no usable refresh tokens (only preimages of hashes), and
`compare_digest` removes the **timing side channel** that a plain `==` comparison would
open. The frontend runs a 401 → refresh-exchange → retry handshake
(`apps/web/lib/api.ts`), so access tokens can stay short-lived.

---

## 7. Payment Webhook Authenticity — HMAC-SHA256

**File:** `apps/api/app/modules/commerce/gateway.py`

```
expected = hex( HMAC-SHA256( key = gateway_secret, msg = raw_body ) )
verified = hmac.compare_digest(expected, X-Signature header)
```

- The webhook — not the client redirect — is the **authoritative** final payment state
  (design doc §18). The signature proves the event really came from the gateway and was not
  tampered with in transit.
- `compare_digest` again prevents signature-check timing attacks.
- The `MockPaymentGateway` (clearly labelled, local/dev only) uses the same signing and
  verification path a real gateway would, so the demo exercises the true trust chain.

---

## 8. Webhook Idempotency / Deduplication

**File:** `apps/api/app/modules/commerce/service.py`

- Dedup key: `sha256(f"{provider}:{event_id}")[:12]` stored in `payment_webhook_events`.
- A replayed `(provider, event_id)` pair is detected and **no-oped** — gateways retry
  aggressively, and without this a retried "payment succeeded" event could double-apply.

---

## 9. Payment Idempotency Keys

**File:** `apps/api/app/modules/commerce/service.py` — `create_payment()`, `confirm_mock_payment()`

- A client-supplied `idempotency_key` is looked up before creating a payment; if found and
  owned by another traveller → `PermissionDeniedError` (ownership check prevents key
  squatting/probing). Re-confirming an already-confirmed payment returns the original
  payment (`return payment  # idempotent re-confirm`).
- Missing keys get `auto-{uuid4}`.
- Combined with §8, the payment pipeline is **exactly-once** at the state-transition level:
  network retries and double clicks cannot double-charge or double-confirm.

---

## 10. Server-Side Pricing (integer money)

**File:** `apps/api/app/modules/commerce/service.py` — `create_hotel_booking()`, guide bookings

```
price_paise = room.nightly_rate_paise × nights × rooms_count
```

- All money is **integer paise** (₹1 = 100 paise) — binary floats can represent neither
  0.1 nor 0.01 exactly, so float money accumulates rounding drift; integers never do.
- The total is computed **only from database rates**; client-supplied totals are never
  trusted (a tampered client cannot buy a ₹7,000/night room for ₹1).
- The computed total is frozen onto the booking as a **price snapshot**, so later rate
  edits never mutate historical financial records (design doc §25: history is preserved,
  never destroyed).

---

## 11. Double-Booking Conflict Detection

**File:** `apps/api/app/modules/commerce/service.py`

A guide booking is rejected with `409 Conflict` when the requested service period overlaps
an existing **non-cancelled** booking for the same guide (date-range overlap check against
`guide_availability` + existing bookings). Cancelled bookings release their slot, so
cancellations free capacity without deleting history.

---

## 12. Input Bounds & State-Machine Guards

**Files:** `apps/api/app/modules/commerce/service.py`, `app/modules/planning/service.py`

- Booking horizon: `_validate_horizon()` rejects past dates and dates beyond
  `MAX_BOOKING_HORIZON_DAYS = 365` — bounds the booking table against absurd/far-future
  rows and accidental negative-night pricing.
- Date ordering: `ends_on ≥ starts_on` enforced by a Pydantic `model_validator`
  (`apps/api/app/modules/planning/schemas.py`).
- Enum validation: moods and budget tiers validated against the canonical lists
  (`MOODS`, `BUDGET_TIERS`) — unknown values are 422s, never silently accepted.
- Ownership guards (`_trip_or_404`, `_run_or_404`, `_trip_owned_or_none`): every trip/run/
  booking access verifies `user_id` — **IDOR protection** (a valid ID belonging to another
  user yields 403/404, not data).

---

## 13. Booking State Machine & Conditional Contact Access

**Files:** `apps/api/app/modules/commerce/service.py`, `app/modules/commerce/router.py`

```
PENDING_PAYMENT → CONFIRMED   (payment SUCCEEDED, same DB transaction)
PENDING_PAYMENT → CANCELLED   (payment failed/expired — row kept, never deleted)
Trip: PLANNING → BOOKED → CONFIRMED → COMPLETED | CANCELLED
```

- A succeeded payment flips **all** its bookings `PENDING_PAYMENT → CONFIRMED` inside the
  **same transaction** — the trip can never show confirmed bookings with an unpaid payment
  or vice versa (atomicity is the correctness argument, not application checks).
- **Conditional contact access (design doc §24):** the guide's private email is released
  only when the requester holds a **CONFIRMED (paid) booking**; every release writes an
  append-only `CONTACT_ACCESSED` row to `admin_audit_log`. Login alone never reveals
  private provider contacts — the release is a *transaction-gated* event with an audit
  trail, matching "CONDITIONAL_BOOKING_ACCESS" in the visibility model.

---

## 14. Geo Hierarchy & Ghost-Slug Resolution

**File:** `apps/api/app/modules/geo/router.py`

- The Explore hierarchy (India → State → City → Place) is pure FK-driven filtering:
  `cities?state_id=`, `places?city_id=` — no hardcoded geography anywhere (design rule 6).
- Place detail: `nearby` entries in the editorial `details` payload are **resolved against
  live ACTIVE places at read time**; dead slugs are dropped. A detail page can therefore
  never render a link that 404s, even after content is unpublished.
- Detail routes render as **ISR with `revalidate = 60`** (`apps/web/lib/api.ts` +
  `apps/web/app/explore/[slug]/page.tsx`): editorial content changes only via seeds/admin,
  so a minute of staleness is acceptable in exchange for static-speed rendering; the static
  export build pins the same snapshot at build time for GitHub Pages.

---

## 15. Deterministic Gradient Fallbacks (slug-hashed color)

**File:** `apps/web/app/explore/gradient.ts`

```js
hash = 0
for each char c:  hash = (hash × 31 + charCode(c)) | 0     // 32-bit rolling hash
hue  = |hash| mod 360
hue2 = (hue + 40) mod 360
background = linear-gradient(135deg, hsl(hue 38% 46%), hsl(hue2 45% 30%))
```

Places without verified photography (design rule 8: nothing invented) get a stable
**two-tone gradient derived from their slug**: the same place always renders the same
colors (server and client), and the palette stays within the site's muted tones. The ×31
polynomial rolling hash spreads adjacent slugs (e.g. `puri-beach`, `puri-beach-2`) to
visibly different hues.

---

## 16. Frontend Session-Refresh Handshake

**File:** `apps/web/lib/api.ts`

On any API response with `401`, the client transparently exchanges the stored refresh
token for a new access token and **replays the original request once**; only a failed
refresh logs the user out. Combined with §6 (hashed refresh storage) this keeps access
tokens short-lived without nagging users with re-logins.

---

## 17. ISR / Export Rendering Strategy

**Files:** `apps/web/lib/api.ts`, `apps/web/next.config.ts`, route files under `apps/web/app/`

| Mode | Trigger | Data fetch | Result |
|---|---|---|---|
| Live | normal build | `next: { revalidate: 60 }` | static-speed pages, ≤ 60 s editorial staleness |
| Static export | `STATIC_EXPORT_BASE_PATH` set (GitHub Pages) | `cache: "force-cache"` + `generateStaticParams` | every page prerendered from the build-time API snapshot |

The detail/state/city routes carry both `revalidate = 60` and export-mode
`generateStaticParams`, so **one codebase serves the dynamic local app and the fully static
GitHub Pages demo** (44+ prerendered pages) without forking logic. A `no-store` fetch in a
static-classified route crashes with `DYNAMIC_SERVER_USAGE` — the ISR choice is what keeps
both modes green.

---

## Summary Table

| # | Algorithm | Where | Key constant/formula |
|---|---|---|---|
| 1 | Recommendation scoring | `planning/engine.py` | `3.0·match + 2.0·rating + 1.5·pop + 0.15·gem` |
| 2 | Hidden-gem interleave | `planning/engine.py` | 3 : 1 rhythm, ≥ 25 % share |
| 3 | Itinerary day-split | `planning/service.py` | `per_day = ⌈n/d⌉`, position step 10 |
| 4 | Snapshot + hybrid persistence | `planning/service.py` | snapshot saved per trip/run |
| 5 | Argon2id hashing | `core/security.py` | `CryptContext(schemes=["argon2"])` |
| 6 | JWT + hashed refresh | `core/security.py` | HS256; `sha256`, `compare_digest` |
| 7 | Webhook HMAC | `commerce/gateway.py` | HMAC-SHA256 over raw body |
| 8 | Webhook dedup | `commerce/service.py` | `sha256(provider:event_id)[:12]` |
| 9 | Payment idempotency | `commerce/service.py` | key lookup before create |
| 10 | Server-side pricing | `commerce/service.py` | integer paise, snapshot frozen |
| 11 | Double-booking guard | `commerce/service.py` | range overlap → 409 |
| 12 | Bounds & IDOR guards | commerce/planning services | 365-day horizon, ownership checks |
| 13 | State machine + contact gate | `commerce/service.py` | same-transaction confirm; audited release |
| 14 | Geo FK hierarchy + ghost-slug drop | `geo/router.py` | resolve `nearby` at read time |
| 15 | Slug-hashed gradients | `explore/gradient.ts` | `h = h·31 + c`, hue, hue+40 |
| 16 | Session-refresh handshake | `lib/api.ts` | 401 → refresh → retry once |
| 17 | ISR / export strategy | `lib/api.ts`, route files | `revalidate = 60` / `force-cache` |
