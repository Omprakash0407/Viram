# API contract — first backend increment

Base URL: `/api/v1`. All protected routes require `Authorization: Bearer <access-token>`.

## Discovery

| Method and path | Result |
|---|---|
| `GET /states` | State cards/dropdown data |
| `GET /cities?stateId={uuid}` | Cities in a selected state |
| `GET /places?cityId={uuid}&interest=heritage` | Popular and lesser-known places; include `reason` and public rating |
| `GET /places/{placeId}` | Details, approved media links, public guide summaries |
| `GET /guides?cityId={uuid}&from=YYYY-MM-DD&to=YYYY-MM-DD` | Available, public guide profiles only |

## Planning

`POST /trip-drafts`

```json
{"cityId":"uuid","startsOn":"2026-11-10","endsOn":"2026-11-13","partySize":2,"interests":["heritage","food"]}
```

`POST /trip-drafts/{tripDraftId}/generate-itinerary` returns ranked places. The user may then call `PATCH /trip-drafts/{tripDraftId}/items` to accept, remove or reorder the returned places.

## Checkout

`POST /checkout/holds` takes `tripDraftId`, selected `roomTypeId`, room count and selected `guideId`. It locks hotel rows and guide dates, writes the server-priced selections to `booking_hold_items`, and returns a 10-minute `holdId`, price breakdown and expiry. It never accepts a client-calculated total.

`POST /payments/orders` takes `{ "holdId": "uuid" }`, creates one gateway order per hold, and returns the gateway’s public checkout fields.

`POST /payments/webhooks/razorpay` is gateway-only. Verify the raw-body signature and write `(provider, event_id)` before updating payment/booking state. The browser callback is informational only.

## Confirmed trip

`GET /trips/{bookingId}` returns an itinerary, booking summaries, route/recommendation links and emergency information. It returns provider contact details only when `booking.user_id` equals the authenticated user and `booking.status = CONFIRMED`.

## Non-negotiable response rules

- Monetary values use integer paise—never floating point.
- Every write supports an `Idempotency-Key` header; reuse returns the original result.
- Return `409` for expired holds or unavailable inventory, `403` for another user’s resource, and `422` for valid-but-unbookable input.
- Never return private provider contacts from list, place, draft, hold or failed-payment endpoints.
