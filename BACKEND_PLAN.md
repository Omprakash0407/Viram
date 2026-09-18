# Travel Discovery and Booking Platform — Backend Plan

## 1. Product contract

The system guides a tourist through one uninterrupted journey:

`discover destination → explore curated content → set preferences → choose places/guides → reserve hotel and guide → pay → manage a confirmed trip`

The backend must make the itinerary reproducible, prevent double-booking, keep provider contact details private before verified payment, and return useful trip support information after confirmation.

## 2. MVP boundary

Build these first:

1. India states, cities, destinations and attraction discovery.
2. Preference-based recommendations for popular and lesser-known places.
3. Guide profiles, ratings and availability.
4. Hotel and guide reservation holds, checkout and payment confirmation.
5. A confirmed-trip dashboard: itinerary, route, weather/clothing hints, food/brand suggestions and emergency care.

Use third-party providers rather than building payment, maps, routing, weather or social-media ingestion from scratch.

## 3. Suggested architecture

Start as a modular monolith; it is faster for a student project and can be split into services later.

```text
Web/mobile client
       │ HTTPS + JWT
API application (NestJS/Express + TypeScript)
 ├─ Discovery and content module
 ├─ Planning and recommendation module
 ├─ Inventory and booking module
 ├─ Payment/webhook module
 ├─ Trip dashboard module
 └─ Admin/provider module
       │
PostgreSQL  · Redis (cache/holds/queues) · Object storage (images)
       │
Maps/routing · weather · payment gateway · hotel inventory · permitted social APIs
```

Recommended stack: TypeScript + NestJS, PostgreSQL + Prisma/Drizzle, Redis, BullMQ, S3-compatible object storage, Razorpay for India payments, Google Maps/Mapbox, and OpenWeather. Containerize with Docker; deploy the API and worker separately.

## 4. Core data model

| Area | Main tables | Important fields |
|---|---|---|
| Identity | `users`, `roles`, `sessions` | phone/email verification, role, consent |
| Geography | `states`, `cities`, `destinations`, `attractions` | geo point, category, hidden-gem score, hours, accessibility, safety notes |
| Discovery | `social_content`, `destination_media`, `editorial_reviews` | provider/source URL, embed ID, consent/status, moderation state |
| Guides | `guides`, `guide_languages`, `guide_reviews`, `guide_availability` | verification state, rate, service area, public bio; encrypted private contact |
| Hotels | `hotels`, `room_types`, `hotel_inventory`, `hotel_reviews` | room/date inventory, cancellation rules, supplier reference |
| Planning | `trip_drafts`, `trip_preferences`, `itinerary_days`, `itinerary_items`, `saved_places` | date range, interests, travel pace, source recommendation score |
| Commerce | `booking_holds`, `bookings`, `booking_items`, `payments`, `refunds` | price snapshot, expiry, idempotency key, provider payment ID, state |
| Local support | `restaurants`, `local_brands`, `weather_snapshots`, `health_facilities`, `emergency_numbers`, `route_snapshots` | locality, geo point, source and updated-at |
| Operations | `audit_logs`, `outbox_events`, `webhook_events`, `moderation_reports` | immutable actor/event trail and retry state |

Key relationships: a `trip_draft` has preferences and itinerary items; a confirmed `booking` belongs to a trip; booking items point to a hotel room or guide slot; all displayed recommendations are attached to a location and time window.

## 5. API surface

Use REST initially, versioned as `/api/v1`. Examples:

```text
GET  /states, /cities?stateId=, /destinations?cityId=
GET  /destinations/:id/content
POST /trip-drafts                         # destination + preferences
POST /trip-drafts/:id/generate-itinerary  # ranked places and schedule
PATCH /trip-drafts/:id/items               # accept/remove/reorder items
GET  /guides?cityId=&date=&language=
GET  /hotels?cityId=&checkIn=&checkOut=
POST /checkout/hold                        # atomically hold selected inventory
POST /payments/orders                      # create gateway order for a hold
POST /payments/webhooks/razorpay           # gateway only; signature verified
GET  /trips/:id                            # confirmed trip dashboard
GET  /trips/:id/routes, /recommendations, /emergency
```

The browser never sends the final amount as a trusted value. The server derives every price from the active inventory and stores a price snapshot.

## 6. Critical booking and payment state machine

```text
DRAFT → HELD → PAYMENT_PENDING → PAID → CONFIRMED
                  │                │
                  └→ FAILED         └→ CANCELLED / REFUNDED
HELD → EXPIRED
```

1. Validate dates, availability, party size and provider status.
2. In one database transaction, create a short-lived hold (for example, 10 minutes), decrement/lock inventory, and calculate the final server-side price.
3. Create the payment order using the hold ID as the idempotency key.
4. Treat the payment gateway webhook—not the client redirect—as the source of truth. Verify its signature, deduplicate its event ID, and mark the payment paid transactionally.
5. Create confirmed booking items, publish an outbox event, release or consume the hold, then send confirmations asynchronously.
6. A background worker expires unpaid holds and restores inventory.

Before `CONFIRMED`, public responses expose only a guide's public profile and hotel summary. Private phone/address/contact fields are returned only to the booked traveller after verified payment, and only for their own booking.

## 7. Recommendation logic (start simple)

Do not start with ML. Rank candidates deterministically:

```text
score = interest_match + city_match + availability + rating_quality
      + lesser_known_boost + seasonal_fit + distance_fit - crowd_penalty
```

Return a mixed, explainable list: e.g. 60% popular/high-confidence places and 40% lesser-known places. Store an explanation such as “Matches heritage + craft interests; 4.6 rating; 18 km from your hotel.” Let admins curate the hidden-gem score and seasonal/safety exclusions.

## 8. Integrations and data policy

- Maps/routing: cache route results per itinerary version; show a source timestamp.
- Weather: refresh shortly before travel; derive clothing guidance from weather plus curated local-tradition rules.
- Emergency data: seed verified government/hospital sources, retain source and review date, and always display India emergency number `112` alongside local numbers.
- Social media: store provider post ID, creator attribution, approved embed/link and moderation status. Use official API/OEmbed where permitted; never scrape private or restricted content.
- Hotels: for the MVP, use approved hotel partners/admin-managed inventory; later add an OTA/channel-manager adapter behind an interface.

## 9. Security, privacy and reliability checklist

- JWT access + refresh tokens, RBAC (`tourist`, `guide`, `hotel`, `admin`), and ownership checks on every trip/booking.
- Encrypt sensitive contact/KYC data at rest; keep payment card data out of your system by using gateway-hosted checkout.
- Rate-limit authentication, itinerary generation, checkout and webhooks.
- Verify webhooks, use idempotency keys, database transactions, row locks and an outbox/retry worker.
- Audit administrator/provider edits, refunds, contact-detail access and booking changes.
- Validate all input, use parameterized queries, signed upload URLs and malware checks for media.
- Publish cancellation, privacy, consent and content-takedown policies. Follow applicable Indian privacy/payment requirements before production.
- Monitor failed payments, expired holds, webhook lag, inventory conflicts and route/weather API failures.

## 10. Build sequence

### Sprint 1 — Foundation

Set up repository, Docker, PostgreSQL migrations, authentication/RBAC, admin seed data, states/cities/destinations and media APIs.

### Sprint 2 — Discovery and planning

Add attractions, guide profiles/reviews, preference capture, deterministic recommendation endpoint, editable itinerary drafts and cache.

### Sprint 3 — Booking and payment

Add hotel/guide availability, hold expiry worker, server-side pricing, Razorpay order creation, verified webhook handling, confirmations and refunds/cancellation skeleton.

### Sprint 4 — Confirmed trip dashboard

Build itinerary API, routes, weather/clothing rules, brands/restaurants, health facilities/emergency data and controlled release of provider contact details.

### Sprint 5 — Hardening/demo

Add integration tests for the state machine, webhook replay tests, authorization tests, load test checkout, observability, backups and seeded demo journeys for two states.

## 11. Definition of done for the backend

- A tourist can create a preference-based trip draft, edit the itinerary and choose a guide/hotel.
- The same inventory cannot be sold twice under concurrent checkout attempts.
- Refreshing checkout or receiving a duplicate webhook cannot duplicate a booking or charge.
- A failed/expired payment restores the inventory.
- Contact data cannot be retrieved before payment or by another user.
- A paid booking produces one dashboard with itinerary, route, recommendations, weather guidance and emergency support.
- Admins can update places, guides, inventory and emergency data with an audit trail.
