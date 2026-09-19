/**
 * The full India structure for Explore: every state and union territory.
 * Only states that exist in the API (seeded with editorial data) get live
 * pages; the rest render as links whose target 404s until their content is
 * verified (design rule 8: nothing invented — lesser-known/destination data
 * must be editorially documented first).
 */
export type IndiaState = { name: string; slug: string };

export const INDIA_STATES: IndiaState[] = [
  { name: "Andhra Pradesh", slug: "andhra-pradesh" },
  { name: "Arunachal Pradesh", slug: "arunachal-pradesh" },
  { name: "Assam", slug: "assam" },
  { name: "Bihar", slug: "bihar" },
  { name: "Chhattisgarh", slug: "chhattisgarh" },
  { name: "Goa", slug: "goa" },
  { name: "Gujarat", slug: "gujarat" },
  { name: "Haryana", slug: "haryana" },
  { name: "Himachal Pradesh", slug: "himachal-pradesh" },
  { name: "Jharkhand", slug: "jharkhand" },
  { name: "Karnataka", slug: "karnataka" },
  { name: "Kerala", slug: "kerala" },
  { name: "Madhya Pradesh", slug: "madhya-pradesh" },
  { name: "Maharashtra", slug: "maharashtra" },
  { name: "Manipur", slug: "manipur" },
  { name: "Meghalaya", slug: "meghalaya" },
  { name: "Mizoram", slug: "mizoram" },
  { name: "Nagaland", slug: "nagaland" },
  { name: "Odisha", slug: "odisha" },
  { name: "Punjab", slug: "punjab" },
  { name: "Rajasthan", slug: "rajasthan" },
  { name: "Sikkim", slug: "sikkim" },
  { name: "Tamil Nadu", slug: "tamil-nadu" },
  { name: "Telangana", slug: "telangana" },
  { name: "Tripura", slug: "tripura" },
  { name: "Uttar Pradesh", slug: "uttar-pradesh" },
  { name: "Uttarakhand", slug: "uttarakhand" },
  { name: "West Bengal", slug: "west-bengal" },
  { name: "Andaman & Nicobar Islands", slug: "andaman-and-nicobar-islands" },
  { name: "Chandigarh", slug: "chandigarh" },
  { name: "Dadra & Nagar Haveli and Daman & Diu", slug: "dadra-and-nagar-haveli-and-daman-and-diu" },
  { name: "Delhi", slug: "delhi" },
  { name: "Jammu & Kashmir", slug: "jammu-and-kashmir" },
  { name: "Ladakh", slug: "ladakh" },
  { name: "Lakshadweep", slug: "lakshadweep" },
  { name: "Puducherry", slug: "puducherry" },
];

export const stateHref = (slug: string) => `/explore/state/${slug}`;
export const cityHref = (stateSlug: string, citySlug: string) =>
  `/explore/state/${stateSlug}/city/${citySlug}`;
