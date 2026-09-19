/** Typed client for the VIRĀM FastAPI backend (goes through the Next.js rewrite proxy). */

export const API_BASE = "/api/v1";

/** Base for server-component (RSC) fetches: the browser rewrite proxy is
 *  browser-only, so server code calls the API directly. Static export builds
 *  (GitHub Pages) override it with VIRAM_EXPORT_API_URL for build-time
 *  prerendering. */
export const API_SERVER_BASE =
  process.env.VIRAM_EXPORT_API_URL ??
  process.env.API_INTERNAL_URL ??
  "http://127.0.0.1:8000/api/v1";

/**
 * Server-component fetch. Live mode: no-store, so editorial seed edits show up
 * immediately. Export mode: force-cache — static prerendering forbids no-store,
 * and the build-time snapshot is exactly what the exported site should serve.
 */
export async function serverApi<T>(path: string): Promise<T> {
  const res = await fetch(`${API_SERVER_BASE}${path}`, {
    cache: process.env.STATIC_EXPORT_BASE_PATH ? "force-cache" : "no-store",
  });
  if (!res.ok) {
    throw Object.assign(new Error(`Request failed (${res.status})`), { status: res.status });
  }
  return (await res.json()) as T;
}

// --- token storage -----------------------------------------------------------

const ACCESS_KEY = "viram.access_token";
const REFRESH_KEY = "viram.refresh_token";

export type SessionUser = {
  id: string;
  email: string;
  display_name: string;
  account_role: string;
  status: string;
};

export function getStoredSession(): { access: string; refresh: string } | null {
  if (typeof window === "undefined") return null;
  const access = window.localStorage.getItem(ACCESS_KEY);
  const refresh = window.localStorage.getItem(REFRESH_KEY);
  if (!access || !refresh) return null;
  return { access, refresh };
}

export function storeSession(access: string, refresh: string): void {
  window.localStorage.setItem(ACCESS_KEY, access);
  window.localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearSession(): void {
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}

// --- error shape (unified backend envelope) ----------------------------------

export type ApiError = { code: string; message: string; details?: unknown };

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as { error?: ApiError };
    if (body?.error?.message) {
      return { code: body.error.code ?? "ERROR", message: body.error.message };
    }
  } catch {
    // fall through
  }
  return { code: "HTTP_ERROR", message: `Request failed (${res.status})` };
}

// --- fetch core with one retry on expired access token ------------------------

let refreshInFlight: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  const session = getStoredSession();
  if (!session) return false;
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: session.refresh }),
        });
        if (!res.ok) return false;
        const data = (await res.json()) as {
          access_token: string;
          refresh_token: string;
        };
        storeSession(data.access_token, data.refresh_token);
        return true;
      } catch {
        return false;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

export class HttpError extends Error {
  constructor(
    public status: number,
    public apiError: ApiError,
  ) {
    super(apiError.message);
    this.name = "HttpError";
  }
}

export class AuthRequiredError extends Error {
  constructor() {
    super("Please sign in to continue.");
    this.name = "AuthRequiredError";
  }
}

async function requestOnce(
  path: string,
  init: RequestInit,
  access: string | null,
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (access) headers.set("Authorization", `Bearer ${access}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(`${API_BASE}${path}`, { ...init, headers });
}

/** Authenticated request; transparently refreshes once on 401 then retries. */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const session = getStoredSession();
  let res = await requestOnce(path, init, session?.access ?? null);
  if (res.status === 401 && session) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      const next = getStoredSession();
      res = await requestOnce(path, init, next?.access ?? null);
    }
  }
  if (res.status === 204) return undefined as T;
  if (!res.ok) throw new HttpError(res.status, await parseError(res));
  return (await res.json()) as T;
}

/** Unauthenticated request (no 401 retry). */
export async function publicApi<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await requestOnce(path, init, null);
  if (!res.ok) throw new HttpError(res.status, await parseError(res));
  return (await res.json()) as T;
}

// --- auth ---------------------------------------------------------------------

export type AuthResponse = { user: SessionUser; tokens: { access_token: string; refresh_token: string } };

export async function register(
  email: string,
  password: string,
  display_name: string,
): Promise<AuthResponse> {
  const data = await publicApi<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, display_name }),
  });
  storeSession(data.tokens.access_token, data.tokens.refresh_token);
  return data;
}

export async function login(
  email: string,
  password: string,
): Promise<AuthResponse> {
  const data = await publicApi<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  storeSession(data.tokens.access_token, data.tokens.refresh_token);
  return data;
}

export async function logout(): Promise<void> {
  const session = getStoredSession();
  if (session) {
    try {
      await publicApi("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: session.refresh }),
      });
    } catch {
      // best effort — clear locally regardless
    }
  }
  clearSession();
}

// --- geo ----------------------------------------------------------------------

export type StateRow = { id: string; name: string; slug: string };
export type CityRow = {
  id: string;
  name: string;
  slug: string;
  state_id: string;
  latitude: number;
  longitude: number;
};

export const geoApi = {
  states: () => publicApi<{ items: StateRow[] }>("/geo/states"),
  cities: (stateId?: string) =>
    publicApi<{ items: CityRow[] }>(
      stateId ? `/geo/cities?state_id=${encodeURIComponent(stateId)}` : "/geo/cities",
    ),
  places: (cityId?: string) =>
    publicApi<{ items: PlaceRow[] }>(
      cityId ? `/geo/places?city_id=${encodeURIComponent(cityId)}` : "/geo/places",
    ),
  placeDetail: (slug: string) => publicApi<PlaceDetail>(`/geo/places/${encodeURIComponent(slug)}`),
};

export type PlaceRow = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  city_id: string;
  classification: "POPULAR" | "LESSER_KNOWN";
  lesser_known_note: string | null;
  rating_avg: number | null;
  popularity_score: number | null;
  typical_visit_minutes: number | null;
};

export type PlaceDetailExperience = { title: string; description: string };
export type PlaceDetailGalleryItem = { url: string; caption: string };
export type PlaceDetailReview = {
  author: string;
  rating: number;
  visited: string;
  text: string;
};
export type PlaceDetailNearby = { slug: string; name: string; label: string | null };

/** GET /geo/places/{slug} — full public detail incl. editorial payload. */
export type PlaceDetail = {
  id: string;
  name: string;
  slug: string;
  description: string;
  classification: "POPULAR" | "LESSER_KNOWN";
  lesser_known_note: string | null;
  rating_avg: number | null;
  review_count: number;
  typical_visit_minutes: number | null;
  opening_hours: string | null;
  latitude: number;
  longitude: number;
  city: { name: string; slug: string };
  state: { name: string; slug: string };
  details: {
    tagline?: string;
    eyebrow?: string;
    accent_script?: string;
    about_heading?: string;
    about_body?: string;
    experience_note?: string;
    photo_note?: string;
    gallery_caption?: string;
    experiences?: PlaceDetailExperience[];
    travel_tips?: string[];
    travel_info?: {
      location?: string;
      distance?: string;
      best_time?: string;
      weather?: string;
      ideal_for?: string;
    };
    gallery?: PlaceDetailGalleryItem[];
    sample_reviews?: PlaceDetailReview[];
    nearby?: PlaceDetailNearby[];
  } | null;
};

// --- planning meta --------------------------------------------------------------

export type MoodRow = { key: string; label: string };
export type BudgetRow = { key: string; label: string };

export const planningApi = {
  moods: () => publicApi<{ items: MoodRow[] }>("/planning/moods"),
  budgetTiers: () => publicApi<{ items: BudgetRow[] }>("/planning/budget-tiers"),
};

// --- trips ------------------------------------------------------------------------

export type TripListItem = {
  id: string;
  status: string;
  starts_on: string;
  ends_on: string;
  party_size: number;
};

export type TripCreatePayload = {
  city_id: string;
  starts_on: string; // YYYY-MM-DD
  ends_on: string;
  party_size: number;
  moods: string[];
  budget_tier: string;
};

export type RecommendationItemRow = {
  id?: string;
  place_id: string;
  rank?: number;
  score?: number | null;
  classification: "POPULAR" | "LESSER_KNOWN";
  explanation: string;
  accepted?: boolean;
};

export type ItineraryItemRow = {
  id: string;
  position: number;
  title: string;
  place_id: string | null;
  start_time: string | null;
  duration_minutes: number | null;
  note: string | null;
};

export type ItineraryDayRow = {
  day_number: number;
  date: string;
  items: ItineraryItemRow[];
};

export type TripDetail = {
  id: string;
  status: string;
  city: { id: string; name: string } | null;
  starts_on: string;
  ends_on: string;
  party_size: number;
  preferences: {
    moods?: string[];
    budget_tier?: string;
    party_size?: number;
    days?: number;
  };
  itinerary: {
    id: string;
    status: string;
    days: ItineraryDayRow[];
  } | null;
};

export type PreferencesOut = {
  interests: string[];
  pace: string | null;
  budget_level: string | null;
  notes: string | null;
};

export const usersApi = {
  me: () => api<SessionUser>("/users/me"),
  getPreferences: () => api<PreferencesOut>("/users/me/preferences"),
  updatePreferences: (payload: { interests?: string[] }) =>
    api<unknown>("/users/me/preferences", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
};

export const tripsApi = {
  create: (payload: TripCreatePayload) =>
    api<{ id: string; status: string; starts_on: string; ends_on: string }>(
      "/trips",
      { method: "POST", body: JSON.stringify(payload) },
    ),
  list: () => api<{ items: TripListItem[] }>("/trips"),
  detail: (tripId: string) => api<TripDetail>(`/trips/${tripId}`),
  recommendations: (tripId: string, persist: boolean) =>
    api<{
      run_id: string | null;
      persisted: boolean;
      items: RecommendationItemRow[];
    }>(`/trips/${tripId}/recommendations?persist=${persist}`, { method: "POST" }),
  accept: (tripId: string, runId: string, itemIds: string[]) =>
    api<{ accepted_count: number }>(`/trips/${tripId}/recommendations/accept`, {
      method: "POST",
      body: JSON.stringify({ run_id: runId, item_ids: itemIds }),
    }),
  generateItinerary: (tripId: string, runId: string | null) =>
    api<{ itinerary: TripDetail["itinerary"] }>(`/trips/${tripId}/itinerary`, {
      method: "POST",
      body: JSON.stringify({ run_id: runId }),
    }),
  addCustomItem: (tripId: string, dayNumber: number, title: string, note?: string) =>
    api<{ id: string; position: number; title: string }>(
      `/trips/${tripId}/itinerary/items`,
      {
        method: "POST",
        body: JSON.stringify({
          day_number: dayNumber,
          custom_title: title,
          note: note ?? null,
        }),
      },
    ),
  removeItem: (tripId: string, itemId: string) =>
    api<void>(`/trips/${tripId}/itinerary/items/${itemId}`, { method: "DELETE" }),
};

// --- commerce (Phase 5): hotels, guides, bookings, payments --------------------

export type HotelRow = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  amenities: string[];
  public_phone: string | null;
  public_address: string | null;
  city_id: string;
};

export type RoomTypeRow = {
  id: string;
  hotel_id: string;
  name: string;
  capacity: number;
  nightly_rate_paise: number;
  currency: string;
  declared_units: number | null;
  availability_note: string;
};

export type GuideRow = {
  id: string;
  public_name: string;
  bio: string | null;
  languages: string[];
  expertise: string[];
  areas_served: string[];
  city_id: string | null;
  city_name: string | null;
  day_rate_paise: number | null;
  currency: string;
  review_rating: number | null;
  offered_on?: string[] | null;
};

export type BookingRow = {
  id: string;
  reference_id: string;
  status: string;
  amount_paise: number;
  currency: string;
  hotel_name?: string | null;
  guide_name?: string | null;
  check_in_date?: string;
  check_out_date?: string;
  rooms_count?: number;
  service_start_date?: string;
  service_end_date?: string;
  guide_contact_released?: boolean;
};

export type PaymentRow = {
  id: string;
  gateway: string;
  gateway_order_id: string;
  amount_paise: number;
  currency: string;
  status: string;
  hotel_booking_id: string | null;
  guide_booking_id: string | null;
  mock_checkout: boolean;
};

export const commerceApi = {
  hotels: (cityId: string) =>
    api<{ items: HotelRow[] }>(`/hotels?city_id=${encodeURIComponent(cityId)}`),
  rooms: (hotelId: string) =>
    api<{ hotel: HotelRow; items: RoomTypeRow[] }>(`/hotels/${hotelId}/rooms`),
  guides: (cityId: string) =>
    api<{ items: GuideRow[] }>(`/guides?city_id=${encodeURIComponent(cityId)}`),
  guideAvailability: (guideId: string, month: string) =>
    api<{ available_dates: string[]; unavailable_dates: string[]; note: string }>(
      `/guides/${guideId}/availability?month=${encodeURIComponent(month)}`,
    ),
  createHotelBooking: (payload: {
    hotel_id: string;
    room_type_id: string;
    check_in_date: string;
    check_out_date: string;
    rooms_count: number;
    trip_id: string;
  }) =>
    api<BookingRow & { id: string }>("/hotel-bookings", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createGuideBooking: (payload: {
    guide_profile_id: string;
    service_start_date: string;
    service_end_date: string;
    trip_id: string;
  }) =>
    api<BookingRow & { id: string }>("/guide-bookings", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  tripBookings: (tripId: string) =>
    api<{
      trip_id: string;
      trip_status: string;
      hotel_bookings: BookingRow[];
      guide_bookings: BookingRow[];
    }>(`/trips/${tripId}/bookings`),
  createPayment: (payload: {
    hotel_booking_id?: string;
    guide_booking_id?: string;
    idempotency_key?: string;
  }) =>
    api<PaymentRow>("/payments", { method: "POST", body: JSON.stringify(payload) }),
  mockConfirm: (paymentId: string) =>
    api<PaymentRow & { note: string }>(`/payments/${paymentId}/mock-confirm`, {
      method: "POST",
    }),
  cancelHotelBooking: (bookingId: string) =>
    api<{ id: string; status: string }>(`/hotel-bookings/${bookingId}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason: "cancelled by traveller" }),
    }),
  cancelGuideBooking: (bookingId: string) =>
    api<{ id: string; status: string }>(`/guide-bookings/${bookingId}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason: "cancelled by traveller" }),
    }),
};

export function formatPaise(paise: number, currency = "INR"): string {
  const rupees = paise / 100;
  const symbol = currency === "INR" ? "₹" : `${currency} `;
  return `${symbol}${rupees.toLocaleString("en-IN")}`;
}
